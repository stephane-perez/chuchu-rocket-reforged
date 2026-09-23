"""Generate a reassemblable vasm (Motorola syntax, Devpac-compatible) source
from the unpacked PRG and the traversal result (work/trace.json).

Every address becomes a label: branch targets, PC-relative operands,
relocated longs (code and data), switch-table entries. Data stay as dc.b,
except relocated longs which become dc.l <label>.

usage: emit.py PRG trace.json out.s [--pad N]   (--pad inserts N bytes of nop
       between functions, for the shift test)"""
import sys, os, json, re, struct
sys.path.insert(0, os.path.dirname(__file__))
from prg import PRG
from st_names import hw_name, TRAPS


def split_ops(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def hexval(s):
    neg = s.startswith('-')
    v = int(s.lstrip('-').lstrip('$'), 16)
    return -v if neg else v


class Emitter:
    def __init__(self, prg, tr, names=None, pad=0):
        self.p = prg
        self.tlen, self.dlen, self.blen = prg.tlen, prg.dlen, prg.blen
        self.total = self.tlen + self.dlen + self.blen
        self.img = prg.image
        self.relocs = set(prg.relocs)
        self.ins = {int(k): v for k, v in tr['ins'].items()}
        self.jt = {int(k): v for k, v in tr['jtables'].items()}
        self.cpu030 = set(tr['cpu030'])
        self.calls = set(tr['calls']) | set(tr.get('dead', []))
        self.dead = set(tr.get('dead', []))
        self.owner = {}
        for o, v in self.ins.items():
            for k in range(v['size']):
                self.owner[o + k] = o
        self.names = names or {}
        self.notes = {}
        self.pad = pad
        self.targets = set()
        self.unmatched = []
        self.jt_bytes = {}
        for b, t in self.jt.items():
            if t['kind'] == 'rel16':
                n = 2 * t['count']
            elif t['kind'] == 'sparse':
                n = 4 * t['count']
            else:
                continue
            for k in range(n):
                self.jt_bytes[b + k] = b
        self.func_starts = set()
        self.last_push = None
        self.comment = []

    # ---------- labels
    def collect(self):
        T = self.targets
        T.add(0)
        for r in self.relocs:
            T.add(self.p.long(r))
        for o, v in self.ins.items():
            mn = v['mn']
            for op in split_ops(v['ops']):
                m = re.match(r'^(-?\$[0-9a-f]+)\(pc', op)
                if m:
                    T.add(hexval(m.group(1)))
            if self.is_branch(mn):
                T.add(hexval(split_ops(v['ops'])[-1]))
        for b, t in self.jt.items():
            T.add(b)
            T.update(t.get('targets', []))
        T.update(self.calls)
        for a in list(T):
            if a in self.owner and self.owner[a] != a:
                T.add(self.owner[a])
            if a in self.jt_bytes and self.jt_bytes[a] != a:
                T.add(self.jt_bytes[a])
        self.func_starts = {t for t in self.calls if t in self.ins}
        # boundaries crossed by an 8-bit displacement cannot take padding
        spans = []
        for o, v in self.ins.items():
            mn, ops = v['mn'], v['ops']
            if self.is_branch(mn) and mn.endswith('.b') and not mn.startswith('db'):
                spans.append(sorted((o, hexval(split_ops(ops)[-1]))))
            for op in split_ops(ops):
                m = re.match(r'^(-?\$[0-9a-f]+)\(pc,', op.replace(' ', ''))
                if m:
                    spans.append(sorted((o, hexval(m.group(1)))))
        self.nopad = set()
        for a, b in spans:
            for f in self.func_starts | self.dead:
                if a < f <= b:
                    self.nopad.add(f)

    @staticmethod
    def is_branch(mn):
        base = mn.split('.')[0]
        return (base.startswith('b') and base not in ('btst', 'bchg', 'bclr', 'bset')) or base.startswith('db')

    def name(self, a):
        if a in self.names:
            return self.names[a]
        if a < self.tlen:
            if a in self.jt:
                return 'J_%05x' % a
            if a in self.ins:
                return ('F_%05x' if a in self.calls else 'L_%05x') % a
            return 'T_%05x' % a
        if a < self.tlen + self.dlen:
            return 'D_%05x' % a
        return 'B_%05x' % a

    def expr(self, a):
        """label expression for address a (image offset)."""
        if a < self.tlen and a in self.owner and self.owner[a] != a:
            s = self.owner[a]
            return '%s+%d' % (self.name(s), a - s)
        if a < self.tlen and a in self.jt_bytes and self.jt_bytes[a] != a:
            s = self.jt_bytes[a]
            return '%s+%d' % (self.name(s), a - s)
        if a < 0 or a > self.total:
            raise ValueError('target out of image %x' % a)
        return self.name(a)

    def is_label(self, a):
        return a in self.targets and not (a in self.owner and self.owner[a] != a) \
            and not (a in self.jt_bytes and self.jt_bytes[a] != a)

    # ---------- instructions
    def render(self, o):
        v = self.ins[o]
        mn, ops = v['mn'], v['ops']
        size = v['size']
        base = mn.split('.')[0]
        if mn.endswith('.b') and self.is_branch(mn) and not base.startswith('db'):
            mn = mn[:-2] + '.s'
        if base == 'move' and 'usp' in ops:
            mn = 'move.l'
        if base in ('btst', 'bchg', 'bclr', 'bset'):
            last = split_ops(ops)[-1]
            mn = base + ('.l' if re.match(r'^d[0-7]$', last) else '.b')
        relv = []
        for k in range(2, size - 3, 2):
            if (o + k) in self.relocs:
                relv.append(struct.unpack('>I', self.img[o + k:o + k + 4])[0])
        out = []
        self.comment = []
        oplist = split_ops(ops)
        for op in oplist:
            m = re.match(r'^\$([0-9a-f]+)\.[wl]$', op)
            if m:
                hn = hw_name(int(m.group(1), 16))
                if hn:
                    self.comment.append(hn)
        if base == 'trap' and self.last_push is not None:
            t = int(oplist[0][2:], 16)
            if t in TRAPS:
                nm = TRAPS[t][1].get(self.last_push)
                self.comment.append('%s %s' % (TRAPS[t][0], nm or '$%x' % self.last_push))
        m = re.match(r'^#\$([0-9a-f]+),-\(a7\)$', ops.replace(' ', ''))
        self.last_push = int(m.group(1), 16) if (m and mn == 'move.w') else (self.last_push if base == 'trap' else None)
        for idx, op in enumerate(oplist):
            last = idx == len(oplist) - 1
            if self.is_branch(mn) and last:
                out.append(self.expr(hexval(op)))
                continue
            m = re.match(r'^(-?\$[0-9a-f]+)\(pc(.*)\)$', op.replace(' ', ''))
            if m:
                out.append('%s(pc%s)' % (self.expr(hexval(m.group(1))), m.group(2)))
                continue
            m = re.match(r'^\$([0-9a-f]+)\.l$', op)
            if m:
                val = int(m.group(1), 16)
                if relv and relv[0] == val:
                    relv.pop(0)
                    out.append('(%s).l' % self.expr(val))
                else:
                    out.append(op)
                continue
            m = re.match(r'^\$([0-9a-f]+)\.w$', op)
            if m:
                val = int(m.group(1), 16)
                out.append('$%x.w' % (val | 0xffff0000 if val >= 0x8000 else val))
                continue
            m = re.match(r'^#\$([0-9a-f]+)$', op)
            if m:
                val = int(m.group(1), 16)
                if relv and relv[0] == val and mn.endswith('.l'):
                    relv.pop(0)
                    out.append('#' + self.expr(val))
                elif base == 'moveq':
                    out.append('#%d' % (val - 256 if val >= 128 else val))
                else:
                    out.append(op)
                continue
            out.append(op.replace(', ', ','))
        if relv:
            self.unmatched.append((o, mn, ops, relv))
        return mn, ','.join(out)

    def string_at(self, o):
        """length (incl. NUL) of a printable string starting at o that does not
        cross a label, a relocation or code; 0 if none."""
        end = o
        lim = self.tlen + self.dlen
        while end < lim and 32 <= self.img[end] < 127:
            if end > o and (self.is_label(end) or end == self.tlen):
                return 0
            if end in self.relocs or (end < self.tlen and (end in self.ins or end in self.jt)):
                return 0
            end += 1
        if end - o < 4 or end >= lim or self.img[end] != 0 or (end > o and self.is_label(end)) or end in self.relocs:
            return 0
        return end - o + 1

    @staticmethod
    def quote(t):
        parts = t.split('"')
        return ',$22,'.join('"%s"' % x for x in parts).replace(',"",', ',').replace('"",', '').replace(',""', '')

    # ---------- main
    def emit(self, f):
        self.collect()
        w = f.write
        w('; Chu Chu Rocket (Reservoir Gods, 2002) - reassemblable source\n')
        w('; generated by tools/emit.py from the unpacked CHUCHU.TOS\n')
        w('; assemble: vasmm68k_mot -Ftos -nosym -no-opt -m68000 -tos-flags=6\n\n')
        w('\tsection\ttext,code\n')
        o = 0
        while o < self.tlen + self.dlen:
            if o == self.tlen:
                w('\n\tsection\tdata,data\n')
            if self.is_label(o):
                if o in self.func_starts or o in self.dead:
                    if self.pad and 0 < o < self.tlen and o not in self.nopad:
                        self.padded = getattr(self, 'padded', 0) + 1
                        w('\tdcb.w\t%d,$4e71\t; shift-test padding\n' % (self.pad // 2))
                    w('\n' + ('; unreferenced (dead code)\n' if o in self.dead else ''))
                    if o in self.notes:
                        w('; %s\n' % self.notes[o])
                w('%s:\n' % self.name(o))
            if o < self.tlen and o in self.ins:
                mn, ops = self.render(o)
                c = ''
                if o in self.cpu030:
                    w('\tmc68030\n')
                c = ('\t; ' + ', '.join(self.comment)) if self.comment else ''
                w('\t%s\t%s%s\n' % (mn, ops, c) if ops else '\t%s%s\n' % (mn, c))
                if o in self.cpu030:
                    w('\tmc68000\n')
                o += self.ins[o]['size']
                continue
            if o < self.tlen and o in self.jt:
                t = self.jt[o]
                if t['kind'] == 'rel16':
                    for tg in t['targets']:
                        w('\tdc.w\t%s-%s\n' % (self.expr(tg), self.name(o)))
                    o += 2 * t['count']
                    continue
                if t['kind'] == 'sparse':
                    w('\tdc.w\t%s\n' % ','.join('%d' % x for x in t['values']))
                    for tg in t['targets']:
                        w('\tdc.w\t%s-%s\n' % (self.expr(tg), self.name(o)))
                    o += 4 * t['count']
                    continue
            if o in self.relocs:
                w('\tdc.l\t%s\n' % self.expr(self.p.long(o)))
                o += 4
                continue
            # printable C string ?
            sl = self.string_at(o)
            if sl:
                txt = self.img[o:o + sl - 1].decode('latin1')
                w('\tdc.b\t%s,0\n' % self.quote(txt))
                o += sl
                continue
            # raw data run
            run = []
            while o < self.tlen + self.dlen and len(run) < 16:
                if run and (self.is_label(o) or o == self.tlen):
                    break
                if o in self.relocs or (o < self.tlen and (o in self.ins or o in self.jt)):
                    break
                run.append(self.img[o])
                o += 1
            w('\tdc.b\t%s\n' % ','.join('$%02x' % b for b in run))
        # bss
        w('\n\tsection\tbss,bss\n')
        bl = sorted(a for a in self.targets if a >= self.tlen + self.dlen)
        cur = self.tlen + self.dlen
        for a in bl:
            if a > cur:
                w('\tds.b\t%d\n' % (a - cur))
                cur = a
            w('%s:\n' % self.name(a))
        end = self.total
        if end > cur:
            w('\tds.b\t%d\n' % (end - cur))
        w('\n\tend\n')


def main():
    args = sys.argv[1:]
    pad = 0
    if '--pad' in args:
        i = args.index('--pad')
        pad = int(args[i + 1])
        del args[i:i + 2]
    names, notes = {}, {}
    here = os.path.dirname(os.path.abspath(__file__))
    gl = os.path.join(os.path.dirname(os.path.abspath(args[1])), 'names_godlib.json')
    if os.path.exists(gl):
        for k, v in json.load(open(gl)).items():
            names[int(k)] = v
            notes[int(k)] = '%s : identifie par comparaison avec les sources GodLib' % v
    for line in open(os.path.join(here, 'names.txt')):
        line = line.split('#')[0].split()
        if len(line) >= 2:
            off, nm = int(line[0], 16), line[1]
            names[off] = nm.rstrip('?')
            notes[off] = nm.rstrip('?') + (' (nom suppose)' if nm.endswith('?') else '')
    p = PRG(open(args[0], 'rb').read())
    tr = json.load(open(args[1]))
    e = Emitter(p, tr, names=names, pad=pad)
    e.notes = notes
    with open(args[2], 'w') as f:
        e.emit(f)
    print('labels %d, unmatched relocs %d, padded boundaries %d' % (len(e.targets), len(e.unmatched), getattr(e, 'padded', 0)))
    for u in e.unmatched[:20]:
        print('  unmatched', hex(u[0]), u[1], u[2], [hex(x) for x in u[3]])


if __name__ == '__main__':
    main()
