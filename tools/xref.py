#!/usr/bin/env python3
"""Cross-reference browser for src/chuchu.s (reverse-engineering aid).

  python tools/xref.py NAME            summary of a function (callers, callees,
                                       globals, strings, calls in the demo profile)
  python tools/xref.py NAME --tree 3   call tree below NAME
  python tools/xref.py NAME --up 3     callers above NAME
  python tools/xref.py --global B_xxx  who reads / writes a global
  python tools/xref.py --hot 40        functions sorted by calls in the profile
  python tools/xref.py NAME --src      print the function source

A "function" is a label that is the target of jsr/bsr (or a named label that
is not L_/J_/T_/D_/B_); it extends to the next function label.
Profile counts come from perf/work/prefb2_prof.txt (REFORGED build, STE demo),
matched by address, so they stay valid after labels are renamed."""
import os, re, sys, struct, subprocess, tempfile, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'chuchu.s')
LOCAL = re.compile(r'^(L|J|T)_[0-9a-f]{5}$')
DATA = re.compile(r'^(D|B)_[0-9a-f]{5}$')


def parse():
    lines = open(SRC, encoding='latin1').read().split('\n')
    labels = []          # (line_no, name)
    for i, l in enumerate(lines):
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):', l)
        if m:
            labels.append((i, m.group(1)))
    calls_to = set()
    for l in lines:
        m = re.match(r'^\s+(jsr|bsr\.[sw])\s+\(?([A-Za-z_][A-Za-z0-9_]*)', l)
        if m:
            calls_to.add(m.group(2))
    in_data = False
    funcs = []
    sect = {}
    cur = 'text'
    for i, l in enumerate(lines):
        m = re.match(r'^\s+section\s+(\w+)', l)
        if m:
            cur = m.group(1)
        sect[i] = cur
    for i, name in labels:
        if sect.get(i) != 'text':
            continue
        if name in calls_to or not (LOCAL.match(name) or DATA.match(name) or name.startswith('.')):
            if not LOCAL.match(name) or name in calls_to:
                funcs.append((i, name))
    funcs.sort()
    bodies = {}
    for k, (i, name) in enumerate(funcs):
        end = funcs[k + 1][0] if k + 1 < len(funcs) else len(lines)
        # stop at section change
        for j in range(i, end):
            if re.match(r'^\s+section\s', lines[j]):
                end = j
                break
        bodies[name] = (i, end)
    # strings: D_ labels followed by dc.b "..."
    strings = {}
    for idx, (i, name) in enumerate(labels):
        if DATA.match(name) and i + 1 < len(lines):
            m = re.match(r'^\s+dc\.b\s+"([^"]*)"', lines[i + 1])
            if m:
                strings[name] = m.group(1)
    return lines, bodies, strings


def analyse(lines, bodies):
    info = {}
    for name, (a, b) in bodies.items():
        callees, reads, writes = [], collections.Counter(), collections.Counter()
        for l in lines[a:b]:
            code = l.split(';')[0]
            m = re.match(r'^\s+(jsr|bsr\.[sw])\s+\(?([A-Za-z_][A-Za-z0-9_]*)', code)
            if m:
                callees.append(m.group(2))
            m = re.match(r'^\s+(\S+)\s+(.*)$', code)
            if not m:
                continue
            ops = m.group(2)
            refs = re.findall(r'\b([DB]_[0-9a-f]{5}|[A-Z][A-Za-z0-9_]+)\b', ops)
            parts = ops.split(',')
            for r in refs:
                if r in bodies or LOCAL.match(r):
                    continue
                if len(parts) > 1 and r in parts[-1] and not m.group(1).startswith(('cmp', 'tst', 'btst', 'lea', 'pea')):
                    writes[r] += 1
                else:
                    reads[r] += 1
        info[name] = dict(callees=callees, reads=reads, writes=writes, lines=(a, b))
    callers = collections.defaultdict(list)
    for n, d in info.items():
        for c in d['callees']:
            callers[c].append(n)
    return info, callers


def profile_counts(funcs=None):
    """name -> (calls, cycles) using the REFORGED symbol addresses."""
    prof = os.path.join(ROOT, 'perf', 'work', 'prefb2_prof.txt')
    if not os.path.exists(prof):
        return {}
    tmp = tempfile.mktemp(suffix='.prg')
    subprocess.run([os.environ.get('VASM', 'vasmm68k_mot'), '-Ftos', '-no-opt', '-m68000', '-quiet',
                    '-DREFORGED=1', '-o', tmp, SRC], check=True, capture_output=True)
    raw = open(tmp, 'rb').read()
    os.remove(tmp)
    _, tl, dl, bl, sl = struct.unpack('>HIIII', raw[:18])
    st = raw[28 + tl + dl:28 + tl + dl + sl]
    addr, i = {}, 0
    while i < len(st):
        nm = st[i:i + 8]
        typ, val = struct.unpack('>HI', st[i + 8:i + 14])
        i += 14
        if typ & 0x48 == 0x48:
            nm += st[i:i + 14]
            i += 14
        if typ & 0x0200:
            addr[val] = nm.rstrip(b'\0').decode('latin1')
    text, cnt, cyc = None, {}, {}
    for l in open(prof):
        m = re.match(r'PROGRAM_TEXT:\s+0x([0-9a-f]+)', l)
        if m:
            text = int(m.group(1), 16)
        m = re.match(r'^([0-9a-f]{8}) .*\((\d+), (\d+), \d+, \d+\)$', l)
        if m:
            a = int(m.group(1), 16) - text
            cnt[a] = int(m.group(2))
            cyc[a] = int(m.group(3))
    starts = sorted(a for a, n in addr.items() if funcs is None or n in funcs)
    import bisect
    fcyc = collections.Counter()
    for a, c in cyc.items():
        k = bisect.bisect_right(starts, a) - 1
        if k >= 0:
            fcyc[addr[starts[k]]] += c
    return {n: (cnt.get(a, 0), fcyc.get(n, 0)) for a, n in addr.items() if funcs is None or n in funcs}


def main():
    args = sys.argv[1:]
    lines, bodies, strings = parse()
    info, callers = analyse(lines, bodies)
    prof = profile_counts(set(bodies))
    total = sum(c for _, c in prof.values()) or 1

    def pc(n):
        c = prof.get(n)
        return '' if not c else ' [%d calls, %.1f%%]' % (c[0], 100 * c[1] / total)

    if '--hot' in args:
        k = int(args[args.index('--hot') + 1])
        for n, (c, y) in sorted(prof.items(), key=lambda x: -x[1][0])[:k]:
            if n in bodies:
                print('%8d  %5.1f%%  %s' % (c, 100 * y / total, n))
        return
    if '--global' in args:
        g = args[args.index('--global') + 1]
        for n, d in sorted(info.items()):
            if d['reads'][g] or d['writes'][g]:
                print('%-28s read %d  write %d%s' % (n, d['reads'][g], d['writes'][g], pc(n)))
        return
    name = args[0]
    if name not in info:
        sys.exit('unknown function %s' % name)
    if '--src' in args:
        a, b = info[name]['lines']
        print('\n'.join(lines[a:b]))
        return
    if '--tree' in args or '--up' in args:
        up = '--up' in args
        depth = int(args[args.index('--up' if up else '--tree') + 1])
        seen = set()

        def walk(n, d, pre):
            print(pre + n + pc(n))
            if d == 0 or n in seen:
                return
            seen.add(n)
            nxt = sorted(set(callers[n])) if up else list(dict.fromkeys(info.get(n, {}).get('callees', [])))
            for c in nxt:
                walk(c, d - 1, pre + '  ')
        walk(name, depth, '')
        return
    d = info[name]
    a, b = d['lines']
    print('%s  (source lines %d-%d, %d lines)%s' % (name, a + 1, b, b - a, pc(name)))
    print('callers :', ', '.join(sorted(set(callers[name]))) or '-')
    print('callees :', ', '.join(dict.fromkeys(d['callees'])) or '-')
    g = sorted(set(list(d['reads']) + list(d['writes'])))
    print('globals :', ', '.join('%s%s' % (x, '(w)' if d['writes'][x] else '') for x in g if not x in strings) or '-')
    ss = [x for x in g if x in strings]
    if ss:
        print('strings :', ', '.join('%s="%s"' % (x, strings[x]) for x in ss))


if __name__ == '__main__':
    main()
