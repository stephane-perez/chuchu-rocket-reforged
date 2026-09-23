"""CHUCHU.LNK extractor - GodLib LINKFILE, 2001 layout (version 0).
Header : +0 ID $12345678, +4 version, +8 FAT size, +$16 pRoot (FAT-relative)
Folder : U16 fileCount, U16 folderCount, pName, pFiles, pFolders
File   : U32 size, U32 unpackedSize, U32 offset, U16 packedFlag, U16 loadedFlag, pName
Packed files are Pack-Ice 2.40 ('ICE!')."""
import struct, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from unice import unice

def cstr(d, o):
    return d[o:d.index(b'\0', o)].decode('latin1')

def read_folder(d, o, path=''):
    nfiles, nfold, pname, pfiles, pfolds = struct.unpack('>HHIII', d[o:o + 16])
    name = cstr(d, pname)
    here = (path + '/' + name) if name else path
    files = []
    for i in range(nfiles):
        r = pfiles + 20 * i
        size, usize, off, packed, loaded, pn = struct.unpack('>IIIHHI', d[r:r + 20])
        files.append(dict(name=cstr(d, pn), path=here, size=size, unpacked=usize,
                          offset=off, packed=packed, record=r))
    for i in range(nfold):
        files += read_folder(d, pfolds + 16 * i, here)
    return files

def load(path):
    d = open(path, 'rb').read()
    ident, ver, fat = struct.unpack('>III', d[:12])
    assert ident == 0x12345678, hex(ident)
    root = struct.unpack('>I', d[0x16:0x1a])[0]
    return d, dict(version=ver, fat=fat, root=root), read_folder(d, root)

if __name__ == '__main__':
    d, hdr, files = load(sys.argv[1])
    out = sys.argv[2]
    os.makedirs(out + '/packed', exist_ok=True)
    os.makedirs(out + '/files', exist_ok=True)
    for f in files:
        blob = d[f['offset']:f['offset'] + f['size']]
        open(f"{out}/packed/{f['name']}", 'wb').write(blob)
        if f['packed']:
            raw, info = unice(blob)
            assert len(raw) == f['unpacked'] and info['left'] == 0, f
            f['picture_mode'] = info['picture']
        else:
            raw = blob
            assert len(raw) == f['unpacked']
        open(f"{out}/files/{f['name']}", 'wb').write(raw)
    end = max(f['offset'] + f['size'] for f in files)
    json.dump(dict(header=hdr, files=files, file_size=len(d), data_end=end),
              open(out + '/manifest.json', 'w'), indent=1)
    print(hdr, len(files), 'files; data end', end, 'of', len(d))


def build(orig_path, files_dir, out_path):
    """Rebuild a LINKFILE with the same FAT layout.
    Unchanged files reuse their original (Pack-Ice) blob, byte for byte;
    changed files are stored unpacked (packedFlag=0) - the loader
    (Packer_GetType at $1142) only depacks data starting with 'ICE!'/'ATM5'."""
    d, hdr, files = load(orig_path)
    fat = bytearray(d[:hdr['fat']])
    off = hdr['fat']
    blobs = []
    changed = []
    for f in sorted(files, key=lambda f: f['offset']):
        new = open(os.path.join(files_dir, f['name']), 'rb').read()
        blob = d[f['offset']:f['offset'] + f['size']]
        raw = unice(blob)[0] if f['packed'] else blob
        if new == raw:
            size, usize, packed = f['size'], f['unpacked'], f['packed']
        else:
            blob, size, usize, packed = new, len(new), len(new), 0
            changed.append(f['name'])
        struct.pack_into('>IIIHH', fat, f['record'], size, usize, off, packed, 0)
        blobs.append(blob)
        off += size
    out = bytes(fat) + b''.join(blobs)
    open(out_path, 'wb').write(out)
    return changed, len(out)
