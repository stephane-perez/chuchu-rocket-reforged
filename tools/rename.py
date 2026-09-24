#!/usr/bin/env python3
"""Safely rename labels in src/chuchu.s and add header comments.

  python tools/rename.py MAPFILE

MAPFILE lines:
  OLD NEW                       rename label OLD to NEW everywhere (whole word)
  @NAME text...                 add a comment line above label NAME
                                (several @NAME lines are kept in order)
Blank lines and lines starting with # are ignored.

After editing, every build variant is assembled and the plain build is
checked against the original executable: renaming must never change a byte."""
import os, re, sys, subprocess, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'chuchu.s')


def main():
    ren, notes = [], collections.OrderedDict()
    for line in open(sys.argv[1], encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.startswith('@'):
            name, _, text = line[1:].partition(' ')
            notes.setdefault(name, []).append(text)
            continue
        old, new = line.split()[:2]
        ren.append((old, new))
    s = open(SRC, encoding='latin1').read()
    labels = set(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*):', s, re.M))
    for old, new in ren:
        if old not in labels:
            sys.exit('label not found: %s' % old)
        if new in labels and new != old:
            sys.exit('label already exists: %s' % new)
        if len(new) > 22 and not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', new):
            sys.exit('bad label: %s' % new)
        s = re.sub(r'\b%s\b' % re.escape(old), new, s)
        labels.discard(old)
        labels.add(new)
    for name, texts in notes.items():
        pat = re.compile(r'^%s:' % re.escape(name), re.M)
        m = pat.search(s)
        if not m:
            sys.exit('label not found for comment: %s' % name)
        start = m.start()
        # drop an existing header block written by this tool (lines starting with ';;')
        prev = s.rfind('\n', 0, start - 1)
        block_start = start
        while True:
            ls = s.rfind('\n', 0, block_start - 1) + 1
            if s[ls:block_start].startswith(';;'):
                block_start = ls
            else:
                break
        header = ''.join(';; %s\n' % t if t else ';;\n' for t in texts)
        s = s[:block_start] + header + s[start:]
    open(SRC, 'w', encoding='latin1').write(s)
    print('renamed %d labels, %d header comments' % (len(ren), len(notes)))
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'build.py'), '--check'], capture_output=True, text=True)
    ok = r.stdout.count('IDENTICAL') == 2
    print('build --check :', 'IDENTICAL' if ok else 'FAILED\n' + r.stdout + r.stderr)
    for d in (['REFORGED'], ['REFORGED', 'BLIT_CHECK'], ['OPTIM', 'SKIP_INTRO']):
        r2 = subprocess.run(['vasmm68k_mot', '-Ftos', '-nosym', '-no-opt', '-m68000', '-quiet', '-o', os.devnull, SRC]
                            + ['-D%s=1' % x for x in d], capture_output=True, text=True)
        if r2.returncode:
            ok = False
            print('assembly failed with', d, r2.stdout[-500:], r2.stderr[-500:])
    subprocess.run([sys.executable, os.path.join(ROOT, 'build.py')], capture_output=True)
    if ok:
        r3 = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'codemap.py')], capture_output=True, text=True)
        print(r3.stdout.strip() or r3.stderr.strip())
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
