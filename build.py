#!/usr/bin/env python3
"""Build Chu Chu Rocket for the Atari ST from src/ and assets/.

  python build.py                  -> out/CHUCHU.TOS + out/CHUCHU.LNK
  python build.py -D SKIP_INTRO    -> same, with a conditional-assembly option
  python build.py --check          -> build, then compare with the originals

Needs vasmm68k_mot (vasm, Motorola syntax) in the PATH, Python 3 and Pillow.
The executable is written unpacked (Pack-Ice is not needed to run it)."""
import argparse, os, subprocess, sys, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import assets as A
import linkfile as L
from unice import unice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-D', action='append', default=[], help='define a symbol (e.g. SKIP_INTRO)')
    ap.add_argument('--check', action='store_true', help='compare output with the original files')
    ap.add_argument('--vasm', default=os.environ.get('VASM', 'vasmm68k_mot'))
    a = ap.parse_args()

    out = os.path.join(ROOT, 'out')
    tmp = os.path.join(ROOT, 'out', 'tmp')
    os.makedirs(tmp, exist_ok=True)

    # 1. code
    cmd = [a.vasm, '-Ftos', '-nosym', '-no-opt', '-m68000', '-tos-flags=6', '-quiet',
           '-o', os.path.join(out, 'CHUCHU.TOS'), os.path.join(ROOT, 'src', 'chuchu.s')]
    cmd += ['-D%s=1' % d if '=' not in d else '-D' + d for d in a.D]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit('vasm failed:\n' + r.stdout + r.stderr)
    print('code   : out/CHUCHU.TOS (%d bytes)%s' % (os.path.getsize(os.path.join(out, 'CHUCHU.TOS')),
                                                   ' defines: ' + ','.join(a.D) if a.D else ''))

    # 2. data: assets/ (PNG + raw files) -> binary files -> CHUCHU.LNK
    files = os.path.join(tmp, 'files')
    if os.path.exists(files):
        shutil.rmtree(files)
    orig_lnk = os.path.join(ROOT, 'orig', 'CHUCHU.LNK')
    _, _, entries = L.load(orig_lnk)
    ref = os.path.join(tmp, 'ref')
    os.makedirs(ref, exist_ok=True)
    d = open(orig_lnk, 'rb').read()
    for e in entries:             # original file list, used for names/order
        blob = d[e['offset']:e['offset'] + e['size']]
        open(os.path.join(ref, e['name']), 'wb').write(unice(blob)[0] if e['packed'] else blob)
    A.import_all(os.path.join(ROOT, 'assets'), ref, files)
    changed, size = L.build(orig_lnk, files, os.path.join(out, 'CHUCHU.LNK'))
    print('data   : out/CHUCHU.LNK (%d bytes), %d modified file(s) %s' % (size, len(changed), changed))

    if a.check:
        u = open(os.path.join(ROOT, 'orig', 'CHUCHU.TOS'), 'rb').read()
        ref_prg = unice(u[u.index(b'ICE!'):])[0]
        same_code = open(os.path.join(out, 'CHUCHU.TOS'), 'rb').read() == ref_prg
        same_lnk = open(os.path.join(out, 'CHUCHU.LNK'), 'rb').read() == d
        print('check  : code %s the unpacked original, data %s the original'
              % ('IDENTICAL to' if same_code else 'differs from', 'IDENTICAL to' if same_lnk else 'differs from'))
        if not (same_code and same_lnk) and not (a.D or changed):
            sys.exit(1)
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
