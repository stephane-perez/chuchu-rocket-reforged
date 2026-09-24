"""Assemble src with symbols, extract function-level symbols as an nm-style file (TEXT-relative)."""
import sys, struct, subprocess, re, tempfile, os
tmp = tempfile.mktemp(suffix='.prg')
src, out = sys.argv[1], sys.argv[2]
defs = sys.argv[3:]
subprocess.run(['vasmm68k_mot', '-Ftos', '-no-opt', '-m68000', '-tos-flags=6', '-quiet', '-o', tmp, src] + ['-D%s=1' % d for d in defs], check=True)
d = open(tmp, 'rb').read(); os.remove(tmp)
_, tl, dl, bl, sl = struct.unpack('>HIIII', d[:18])
st = d[28 + tl + dl:28 + tl + dl + sl]
n = 0
with open(out, 'w') as f:
    i = 0
    while i < len(st):
        name = st[i:i + 8]
        typ, val = struct.unpack('>HI', st[i + 8:i + 14])
        i += 14
        if typ & 0x48 == 0x48:          # extended (GST) name: next 14 bytes continue it
            name += st[i:i + 14]
            i += 14
        name = name.rstrip(b'\0').decode('latin1')
        if typ & 0x0200 and (name.startswith('F_') or re.match(r'^[A-Z][a-z]', name)):   # text
            f.write('%08x T %s\n' % (val, name)); n += 1
print(n, 'symbols')
