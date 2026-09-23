"""Name functions of the binary by matching them against GodLib's assembler
sources (ref/GODLIB/**/*.S), plus GEMDOS/XBIOS/BIOS trap wrappers.

Matching key: sequence of normalised mnemonics (no operands), so relocation
and label addresses do not matter. A match needs >= MIN_INS identical
instructions from the function entry, and must be unique.
Output: work/names.json  {offset: name}  and a report."""
import sys, os, re, json, glob, collections
sys.path.insert(0, os.path.dirname(__file__))

MIN_INS = 6
ALIAS = {'movea': 'move', 'adda': 'add', 'suba': 'sub', 'cmpa': 'cmp', 'addi': 'add', 'subi': 'sub',
         'cmpi': 'cmp', 'andi': 'and', 'ori': 'or', 'eori': 'eor', 'dbf': 'dbra', 'cmpm': 'cmp',
         'addq': 'addq', 'subq': 'subq', 'bhs': 'bcc', 'blo': 'bcs'}


def norm(mn):
    base = mn.lower().split('.')[0]
    return ALIAS.get(base, base)


def parse_S(path):
    """-> {label: [mnemonics]} for exported labels."""
    txt = open(path, encoding='latin1').read().replace('\r', '')
    exports = set(re.findall(r'^\s+export\s+(\w+)', txt, re.M))
    funcs = {}
    cur = None
    for line in txt.split('\n'):
        line = line.split(';')[0]
        if not line.strip() or line.lstrip().startswith('*'):
            continue
        m = re.match(r'^(\w+):?\s*(.*)$', line)
        if m and not line[0].isspace():
            lab = m.group(1)
            if lab in exports:
                cur = lab
                funcs[cur] = []
            elif cur is None:
                continue
            rest = m.group(2).strip()
            if not rest:
                continue
            line = '\t' + rest
        if cur is None:
            continue
        toks = line.split()
        if not toks:
            continue
        mn = toks[0]
        if mn.lower() in ('dc.b', 'dc.w', 'dc.l', 'ds.b', 'ds.w', 'ds.l', 'even', 'text', 'data', 'bss',
                          'offset', 'export', 'import', 'include', 'section', 'end', 'rsreset', 'rs.b',
                          'rs.w', 'rs.l', 'equ', 'set', 'macro', 'endm', 'opt', 'align', 'cnop', 'dcb.b', 'dcb.w'):
            if mn.lower() in ('dc.b', 'dc.w', 'dc.l', 'ds.b', 'ds.w', 'ds.l', 'data', 'bss'):
                funcs[cur].append('#DATA')
            continue
        if len(toks) > 1 and toks[1].lower() in ('equ', 'set', '=', 'rs.b', 'rs.w', 'rs.l'):
            continue
        funcs[cur].append(norm(mn))
    out = {}
    for k, v in funcs.items():
        if '#DATA' in v:
            v = v[:v.index('#DATA')]
        if v:
            out[k] = v
    return out


def binary_funcs(tr, starts):
    ins = {int(k): v for k, v in tr['ins'].items()}
    seqs = {}
    for s in starts:
        o, seq = s, []
        while o in ins and len(seq) < 400:
            seq.append(norm(ins[o]['mn']))
            if norm(ins[o]['mn']) in ('rts', 'rte', 'jmp') or ins[o]['mn'].startswith('bra'):
                # keep going: functions can continue after a local bra, but stop at rts/rte
                if norm(ins[o]['mn']) in ('rts', 'rte'):
                    break
            o += ins[o]['size']
        seqs[s] = seq
    return seqs, ins


def common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def main():
    tr = json.load(open(sys.argv[1]))
    root = sys.argv[2]
    out = sys.argv[3]
    lib = {}
    for f in glob.glob(os.path.join(root, '**', '*.S'), recursive=True):
        for k, v in parse_S(f).items():
            lib[k] = (v, os.path.relpath(f, root))
    ins_all = {int(k) for k in tr['ins']}
    starts = set(tr['calls']) | set(tr.get('dead', []))
    # also every instruction following an rts is a potential entry of an asm routine
    ins = {int(k): v for k, v in tr['ins'].items()}
    for o, v in ins.items():
        if norm(v['mn']) in ('rts', 'rte') and (o + v['size']) in ins:
            starts.add(o + v['size'])
    seqs, _ = binary_funcs(tr, starts)
    names = {}
    report = []
    for lab, (lseq, src) in sorted(lib.items()):
        if len(lseq) < MIN_INS:
            continue
        best = []
        for s, bseq in seqs.items():
            n = common_prefix(lseq, bseq)
            full = n == len(lseq)
            if n >= MIN_INS and (full or n >= 0.8 * len(lseq)):
                best.append((full, n, s))
        best.sort(reverse=True)
        if not best:
            continue
        top = [b for b in best if b[:2] == best[0][:2]]
        if len(top) == 1:
            full, n, s = top[0]
            if s not in names:
                names[s] = lab
                report.append((s, lab, src, n, len(lseq), 'exact' if full else 'partial'))
        else:
            report.append((top[0][2], lab, src, top[0][1], len(lseq), 'ambiguous x%d' % len(top)))
    # trap wrappers: short functions doing move.w #n,-(sp) ; trap #k
    TRAPS = {1: 'Gemdos', 13: 'Bios', 14: 'Xbios'}
    json.dump({str(k): v for k, v in names.items()}, open(out, 'w'), indent=1, sort_keys=True)
    ok = [r for r in report if r[5] in ('exact', 'partial')]
    print('GodLib asm exports: %d; matched %d (exact %d)' % (
        len(lib), len(ok), sum(r[5] == 'exact' for r in ok)))
    by = collections.Counter(r[2].split('/')[0] for r in ok)
    print('by module:', dict(by))
    for r in sorted(report)[:400]:
        print('  %05x %-28s %-22s %3d/%-3d %s' % r)


if __name__ == '__main__':
    main()
