#!/usr/bin/env python3
"""Regenerate everything from the original files in orig/ (CHUCHU.TOS, CHUCHU.LNK).
WARNING: overwrites src/chuchu.s and assets/ (hand edits would be lost).

  1. unpack CHUCHU.TOS (Pack-Ice 2.40)           -> work/CHUCHU_U.PRG
  2. extract CHUCHU.LNK (GodLib LINKFILE)        -> work/lnk/files
  3. export graphics to indexed PNG              -> assets/
  4. recursive disassembly                       -> analysis/trace.json
  5. (optional) GodLib name matching, needs ref/GODLIB (git clone
     https://github.com/ReservoirGods/GODLIB ref/GODLIB) -> analysis/names_godlib.json
  6. source generation                           -> src/chuchu.s"""
import os, sys, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'tools')
sys.path.insert(0, T)
from unice import unice

def run(*a):
    print('>', ' '.join(os.path.relpath(x, ROOT) if os.path.isabs(x) else x for x in a))
    subprocess.run([sys.executable] + list(a), check=True)

os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)
os.makedirs(os.path.join(ROOT, 'analysis'), exist_ok=True)
u = open(os.path.join(ROOT, 'orig', 'CHUCHU.TOS'), 'rb').read()
prg = os.path.join(ROOT, 'work', 'CHUCHU_U.PRG')
open(prg, 'wb').write(unice(u[u.index(b'ICE!'):])[0])
print('> unpacked CHUCHU.TOS -> work/CHUCHU_U.PRG')
run(os.path.join(T, 'linkfile.py'), os.path.join(ROOT, 'orig', 'CHUCHU.LNK'), os.path.join(ROOT, 'work', 'lnk'))
run(os.path.join(T, 'assets.py'), 'export', os.path.join(ROOT, 'work', 'lnk', 'files'), os.path.join(ROOT, 'assets'))
run(os.path.join(T, 'trace.py'), prg, os.path.join(ROOT, 'analysis', 'trace.json'))
if os.path.isdir(os.path.join(ROOT, 'ref', 'GODLIB')):
    run(os.path.join(T, 'godlib_match.py'), os.path.join(ROOT, 'analysis', 'trace.json'),
        os.path.join(ROOT, 'ref', 'GODLIB'), os.path.join(ROOT, 'analysis', 'names_godlib.json'))
run(os.path.join(T, 'emit.py'), prg, os.path.join(ROOT, 'analysis', 'trace.json'), os.path.join(ROOT, 'src', 'chuchu.s'))
