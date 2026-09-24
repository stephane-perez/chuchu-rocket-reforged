#!/usr/bin/env python3
"""All the checks that make the source trustworthy.

 1. build (no option)  == original executable (unpacked) and original CHUCHU.LNK, byte for byte
 2. assets export/import round trip: 178 files identical
 3. shift test: regenerate the source with 16 bytes of padding before every
    function (except where an 8-bit displacement crosses), assemble it.
    Running the result in Hatari (run/run.sh) must behave like the original."""
import os, sys, subprocess, json, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'tools')
sys.path.insert(0, T)
from unice import unice
from prg import PRG
import linkfile as L

ok = True
r = subprocess.run([sys.executable, os.path.join(ROOT, 'build.py'), '--check'], capture_output=True, text=True)
print(r.stdout.strip())
ok &= r.returncode == 0 and r.stdout.count('IDENTICAL') == 2

tmp = tempfile.mkdtemp()
d, _, entries = L.load(os.path.join(ROOT, 'orig', 'CHUCHU.LNK'))
os.makedirs(tmp + '/files')
for e in entries:
    blob = d[e['offset']:e['offset'] + e['size']]
    open(tmp + '/files/' + e['name'], 'wb').write(unice(blob)[0] if e['packed'] else blob)
r = subprocess.run([sys.executable, os.path.join(T, 'assets.py'), 'selftest', tmp + '/files'], capture_output=True, text=True)
print('assets :', r.stdout.strip())
ok &= ', 0 differ' in r.stdout

u = open(os.path.join(ROOT, 'orig', 'CHUCHU.TOS'), 'rb').read()
open(tmp + '/u.prg', 'wb').write(unice(u[u.index(b'ICE!'):])[0])
r = subprocess.run([sys.executable, os.path.join(T, 'emit.py'), tmp + '/u.prg', os.path.join(ROOT, 'analysis', 'trace.json'),
                    tmp + '/pad.s', '--pad', '16'], capture_output=True, text=True)
print('shift  :', r.stdout.strip())
vasm = os.environ.get('VASM', 'vasmm68k_mot')
r = subprocess.run([vasm, '-Ftos', '-nosym', '-no-opt', '-m68000', '-tos-flags=6', '-quiet', '-o',
                    os.path.join(ROOT, 'out', 'CHUCHU_SHIFTED.TOS'), tmp + '/pad.s'], capture_output=True, text=True)
p = PRG(open(os.path.join(ROOT, 'out', 'CHUCHU_SHIFTED.TOS'), 'rb').read())
print('shift  : out/CHUCHU_SHIFTED.TOS assembled, text %d bytes (+%d) - run it with run/run.sh' % (p.tlen, p.tlen - 0x19602))
ok &= r.returncode == 0
r = subprocess.run([sys.executable, os.path.join(ROOT, 'build.py'), '-D', 'OPTIM'], capture_output=True, text=True)
print('optim  :', (r.stdout.strip().split('\n') or [''])[0])
ok &= r.returncode == 0
try:
    import unicorn  # noqa
    r = subprocess.run([sys.executable, os.path.join(T, 'difftest.py')], capture_output=True, text=True)
    for line in r.stdout.strip().split('\n'):
        print('diff   :', line)
    ok &= r.returncode == 0
except ImportError:
    print('diff   : (unicorn module missing: pip install unicorn)')
subprocess.run([sys.executable, os.path.join(ROOT, 'build.py')], capture_output=True)
print('RESULT :', 'ALL OK' if ok else 'FAILURE')
sys.exit(0 if ok else 1)
