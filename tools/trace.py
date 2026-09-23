"""Recursive traversal of the unpacked CHUCHU PRG.

Only follows what can execute: entry point, branch/call targets, relocated
pointers into text that decode cleanly, and Pure C switch tables.
Outputs work/trace.json : code instructions, jump tables, coverage."""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import capstone as cs
from prg import PRG

md = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_M68K_000 | cs.CS_MODE_BIG_ENDIAN)
md.detail = True
md30 = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_M68K_030 | cs.CS_MODE_BIG_ENDIAN)
md30.detail = True

TERMINATORS = {'rts', 'rte', 'rtr', 'jmp', 'bra', 'illegal'}
BR_DISP, PCI_DISP, PCI_IDX = 19, 11, 12


BAD_MODES = {9, 10, 14, 15}      # 68020+ memory-indirect modes


def valid_000(ins, b, size):
    """Reject what a 68000 cannot execute but capstone happily decodes.
    capstone reports a brief (d8,An,Xn) with d8=0 as mode 8, so check the fields."""
    try:
        ops = ins.operands
    except cs.CsError:
        return False
    for o in ops:
        if o.type != 3:
            continue
        m = o.address_mode
        if m in BAD_MODES:
            return False
        if m in (7, 8, 12, 13):
            mem = o.mem
            if mem.scale not in (0, 1) or mem.index_reg == 0 or not (-128 <= mem.disp <= 127):
                return False
            if m in (7, 8) and mem.base_reg == 0:
                return False
    op = struct.unpack('>H', b[:2])[0]
    if (op >> 12) == 6 and (op & 0xff) == 0xff:          # bcc.l (68020)
        return False
    mn = ins.mnemonic
    if mn.startswith(('bf', 'cas', 'chk2', 'cmp2', 'pack', 'unpk', 'rtd', 'trap', 'extb', 'bkpt',
                      'callm', 'rtm', 'cinv', 'cpush', 'move16', 'link.l')) and mn != 'trap':
        return False
    if mn in ('divs.l', 'divu.l', 'muls.l', 'mulu.l', 'divsl.l', 'divul.l', 'chk.l'):
        return False
    if mn.startswith('f') or (mn.startswith('p') and not mn.startswith('pea')):
        return False
    return True


def fix_size(ins, b):
    """capstone bug: memory shifts/rotates (1110 xxx 11 ea) lose their extension words."""
    op = struct.unpack('>H', b[:2])[0]
    if (op & 0xf8c0) == 0xe0c0:
        mode, reg = (op >> 3) & 7, op & 7
        ext = {5: 2, 6: 2, 7: {0: 2, 1: 4}.get(reg, 0)}.get(mode, 0)
        return 2 + ext
    return ins.size


class Tracer:
    def __init__(self, prg):
        self.p = prg
        self.text = prg.text
        self.tlen = prg.tlen
        self.relocs = set(prg.relocs)
        self.ins = {}            # offset -> dict
        self.owner = {}          # byte offset -> instruction start
        self.jtables = {}        # table offset -> dict(base, entries)
        self.errors = []
        self.calls = set()
        self.indirect = []       # unresolved computed jumps
        self.cpu030 = set()      # instructions needing 68030 (movec...)
        self.code_refs = set()   # targets referenced as code addresses (lea/pea/#imm)

    def decode(self, off, allow030=False):
        b = self.text[off:off + 10]
        for dis in ((md, md30) if allow030 else (md,)):
            r = list(dis.disasm(b, off, 1))
            if not r:
                continue
            i = r[0]
            if i.mnemonic in ('', 'invalid', 'dc.w'):
                continue
            try:
                i.operands
            except cs.CsError:
                continue
            size = fix_size(i, b)
            if dis is md and not valid_000(i, b, size):
                continue
            if dis is md30:
                if not i.mnemonic.startswith('movec'):
                    continue
                self.cpu030.add(off)
            return i, size
        return None

    def trial(self, start, limit=4000):
        """Decode without committing; True if it reaches a terminator cleanly."""
        seen = set()
        work = [start]
        n = 0
        while work:
            off = work.pop()
            while True:
                if off in seen or off in self.ins:
                    break
                if off < 0 or off >= self.tlen or off & 1:
                    return False
                d = self.decode(off)
                if not d:
                    return False
                i, size = d
                # a relocated long must sit in an extension word, never on an opcode
                if off in self.relocs or (off - 2) in self.relocs:
                    return False
                for k in range(1, size):
                    if (off + k) in self.owner and self.owner[off + k] != off:
                        return False
                seen.add(off)
                n += 1
                if n > limit:
                    return True
                t = self.branch_target(i)
                if t is not None:
                    work.append(t)
                if i.mnemonic.split('.')[0] in TERMINATORS:
                    break
                off += size
        return True

    def branch_target(self, i):
        for o in i.operands:
            if o.type == 8 and o.address_mode == BR_DISP:
                return o.br_disp.disp + i.address + 2
        return None

    def abs_target(self, off, size):
        """relocated absolute operands inside this instruction -> targets"""
        out = []
        for k in range(2, size - 3, 2):
            if (off + k) in self.relocs:
                out.append((off + k, struct.unpack('>I', self.text[off + k:off + k + 4])[0]))
        return out

    def run(self, seeds):
        work = list(seeds)
        while work:
            off = work.pop()
            while True:
                if off in self.ins:
                    break
                if off < 0 or off >= self.tlen or off & 1:
                    self.errors.append(('bad target', off))
                    break
                d = self.decode(off, allow030=True)
                if not d:
                    self.errors.append(('undecodable', off))
                    break
                i, size = d
                clash = [k for k in range(size) if (off + k) in self.owner]
                if clash:
                    self.errors.append(('overlap', off, self.owner[off + clash[0]]))
                    break
                self.ins[off] = dict(size=size, mn=i.mnemonic, ops=i.op_str)
                for k in range(size):
                    self.owner[off + k] = off
                t = self.branch_target(i)
                if t is not None:
                    work.append(t)
                    if i.mnemonic.startswith('bsr'):
                        self.calls.add(t)
                for o in i.operands:
                    if o.type == 3 and o.address_mode == PCI_DISP and i.mnemonic.split('.')[0] in ('lea', 'pea'):
                        self.code_refs.add(o.mem.disp + off + 2)
                for (_, tgt) in self.abs_target(off, size):
                    base = i.mnemonic.split('.')[0]
                    if tgt < self.tlen and (base in ('lea', 'pea') or '#' in i.op_str):
                        self.code_refs.add(tgt)
                    if i.mnemonic in ('jsr', 'jmp') and tgt < self.tlen:
                        work.append(tgt)
                        if i.mnemonic == 'jsr':
                            self.calls.add(tgt)
                if i.mnemonic == 'jmp':
                    self.jump_table(i, off, size, work)
                if i.mnemonic.split('.')[0] in TERMINATORS:
                    break
                off += size

    def jump_table(self, i, off, size, work):
        """Pure C switch: move.w T(pc,dn.w),dn ; jmp T(pc,dn.w) (entries relative to T)."""
        mode = i.operands[0].address_mode
        if mode == PCI_IDX:
            base = i.operands[0].mem.disp + off + 2
            prev = sorted(o for o in self.ins if off - 24 <= o < off)
            n = None
            pc_move = any(self.ins[o]['mn'] == 'move.w' and '(pc,' in self.ins[o]['ops'].replace(' ', '') for o in prev[-1:])
            for o in reversed(prev):
                m, ops = self.ins[o]['mn'], self.ins[o]['ops']
                if m in ('cmp.w', 'cmpi.w') and ops.startswith('#$'):
                    n = int(ops[2:ops.index(',')], 16) + 1
                    break
                if m in ('and.w', 'andi.w') and ops.startswith('#$'):
                    n = int(ops[2:ops.index(',')], 16) + 1
                    break
            sparse = None
            if prev and self.ins[prev[-1]]['mn'] == 'move.w' and '(a0)' in self.ins[prev[-1]]['ops']:
                lea = [o for o in prev if self.ins[o]['mn'] == 'lea.l' and '(pc)' in self.ins[o]['ops']]
                mq = [o for o in prev if self.ins[o]['mn'] == 'moveq']
                if lea and mq:
                    m = int(self.ins[mq[-1]]['ops'].split(',')[0][2:], 16)
                    sparse = m + 1
            if sparse:
                n = sparse
                vals = [struct.unpack('>h', self.text[base + 2 * k:base + 2 * k + 2])[0] for k in range(n)]
                ents = [base + struct.unpack('>h', self.text[base + 2 * n + 2 * k:base + 2 * n + 2 * k + 2])[0] for k in range(n)]
                self.jtables[base] = dict(kind='sparse', count=n, at=off, values=vals, targets=ents)
                work.extend(ents)
            elif pc_move and n:
                # Pure C switch: n words, each relative to base
                ents = [base + struct.unpack('>h', self.text[base + 2 * k:base + 2 * k + 2])[0] for k in range(n)]
                self.jtables[base] = dict(kind='rel16', count=n, at=off, targets=ents)
                work.extend(ents)
            elif struct.unpack('>H', self.text[base:base + 2])[0] == 0x6000:
                # assembler bra.w table (4 bytes per slot)
                k = 0
                while struct.unpack('>H', self.text[base + 4 * k:base + 4 * k + 2])[0] == 0x6000:
                    work.append(base + 4 * k)
                    k += 1
                self.jtables[base] = dict(kind='bra', count=k, at=off)
            else:
                self.indirect.append(dict(at=off, kind='jmp pc-index ?', base=base))
        elif mode in (PCI_DISP,):
            pass
        else:
            self.indirect.append(dict(at=off, kind=i.op_str))


def main():
    p = PRG(open(sys.argv[1], 'rb').read())
    t = Tracer(p)
    t.run([0])
    print('pass1: %d instr, %d bytes, errors %d' % (len(t.ins), len(t.owner), len(t.errors)))
    # relocated pointers to text from anywhere (data, text data-islands)
    added = 0
    for rounds in range(20):
        data_ptrs = {p.long(r) for r in p.relocs if p.long(r) < p.tlen and (r >= p.tlen or r not in t.owner)}
        ptrs = sorted((data_ptrs | t.code_refs) - set(t.owner))
        new = [x for x in ptrs if t.trial(x)]
        if not new:
            break
        t.run(new)
        added += len(new)
    print('pointer seeds added: %d -> %d instr, %d bytes' % (added, len(t.ins), len(t.owner)))
    # dead-code pass: unreferenced functions recognised by their prologue
    PROLOGUES = (0x48e7, 0x4e56, 0x40e7) + tuple(range(0x2f00, 0x2f10)) + tuple(range(0x3f00, 0x3f10))
    dead = []
    for rounds in range(30):
        found = []
        o = 0
        while o < p.tlen:
            if o in t.owner:
                o += 1
                continue
            s0 = o
            while o < p.tlen and o not in t.owner:
                o += 1
            for cand in range(s0 + (s0 & 1), min(o, s0 + 8), 2):
                if struct.unpack('>H', p.text[cand:cand + 2])[0] in PROLOGUES and t.trial(cand):
                    found.append(cand)
                    break
        found = [f for f in found if f not in t.owner]
        if not found:
            break
        t.run(found)
        dead += found
    t.dead = dead
    print('dead-code functions: %d -> %d bytes' % (len(dead), len(t.owner)))
    print('errors', t.errors[:20]); print('nodetail', getattr(t,'nodetail',[])[:10])
    print('indirect jumps', len(t.indirect), t.indirect[:10])
    print('switch tables', len(t.jtables), 'cpu030 instr', sorted(t.cpu030))
    json.dump(dict(ins={str(k): v for k, v in t.ins.items()}, calls=sorted(t.calls),
                   jtables={str(k): v for k, v in t.jtables.items()}, cpu030=sorted(t.cpu030), dead=sorted(t.dead),
                   indirect=t.indirect, errors=t.errors), open(sys.argv[2], 'w'))
    # coverage
    code = len(t.owner)
    gaps = []
    o = 0
    while o < p.tlen:
        if o in t.owner:
            o += 1
            continue
        s = o
        while o < p.tlen and o not in t.owner:
            o += 1
        gaps.append((s, o - s))
    print('text %d bytes, code %d (%.1f%%), %d gaps' % (p.tlen, code, 100 * code / p.tlen, len(gaps)))
    for g in sorted(gaps, key=lambda g: -g[1])[:25]:
        print('  gap %06x len %d : %s' % (g[0], g[1], p.text[g[0]:g[0] + 16].hex()))


if __name__ == '__main__':
    main()
