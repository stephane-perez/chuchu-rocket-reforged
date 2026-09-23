"""Export CHUCHU assets to editable indexed PNGs, and import them back.

  assets.py export <files_dir> <assets_dir>
  assets.py import <assets_dir> <orig_files_dir> <out_files_dir>

PNG conventions (indexed, palette embedded so editors keep the indices):
  .PI1  : 16 colours; the PNG palette IS the ST palette (edit it freely,
          it is converted back to STE 4-bit values).
  .BSB / .GFX : 32 colours. 0-15 = opaque ST colour index,
          16 = transparent, 17-31 = transparent but with a residual colour
          (index-16) OR-ed by the blitter (rare, kept for exactness).
          A .json sidecar describes where each sprite sits in the sheet.
Everything else is copied untouched. An export+import with no edit gives
back the original files byte for byte (checked by `assets.py selftest`)."""
import sys, os, json, struct, glob, shutil
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image
from stgfx import st_pal, planar_to_idx, idx_to_planar

SPRITE_PAL_DEFAULT = 'BOARD.PAL'
SPRITE_PAL = {'ATARI': 'ATARIPAL.PAL', 'FUJI': 'ATARIPAL.PAL', 'BALL': 'ATARIPAL.PAL'}


def rgb_to_st(rgb):
    w = 0
    for sh, v in zip((8, 4, 0), rgb):
        n = round(v / 17)
        w |= (((n >> 1) & 7) | ((n & 1) << 3)) << sh
    return w


def pal_bytes(pal):
    out = []
    for c in pal:
        out += list(c)
    return out


def sprite_palette(files_dir, name):
    key = next((k for k in SPRITE_PAL if name.startswith(k)), None)
    pf = os.path.join(files_dir, SPRITE_PAL.get(key, SPRITE_PAL_DEFAULT))
    pal = st_pal(struct.unpack('>16H', open(pf, 'rb').read()[:32]))
    # 16..31: transparent entries, shown as magenta-ish tints
    return pal + [(255, 0, 255)] + [tuple(min(255, (c + 255) // 2) for c in p) for p in pal[1:]]


# ---------------------------------------------------------------- PI1
def export_pi1(data, png):
    pal = st_pal(struct.unpack('>16H', data[2:34]))
    rows = planar_to_idx(data, 34, 20, 200, 4)
    im = Image.new('P', (320, 200))
    im.putpalette(pal_bytes(pal))
    im.putdata([v for r in rows for v in r])
    im.save(png)
    return {'type': 'PI1', 'header': data[:2].hex(), 'tail': data[34 + 32000:].hex()}


def import_pi1(png, meta):
    im = Image.open(png)
    assert im.mode == 'P' and im.size == (320, 200), 'PI1 PNG must be 320x200 indexed'
    pal = im.getpalette()[:48]
    words = [rgb_to_st(pal[3 * i:3 * i + 3]) for i in range(16)]
    px = list(im.getdata())
    assert max(px) < 16, 'PI1 PNG uses more than 16 colours'
    rows = [px[y * 320:(y + 1) * 320] for y in range(200)]
    return (bytes.fromhex(meta['header']) + struct.pack('>16H', *words) +
            idx_to_planar(rows, 4) + bytes.fromhex(meta['tail']))


# ---------------------------------------------------------------- BSB
def _encode_px(g, m):
    return g if m else 16 + g


def export_bsb(data, png, pal):
    ident, ver, cnt = struct.unpack('>IHH', data[:8])
    ptrs = struct.unpack('>%dI' % cnt, data[8:8 + 4 * cnt])
    sprites = []
    for p in ptrs:
        g, m, w, h, gp, mp = struct.unpack('>IIHHHH', data[p:p + 16])
        ww = (w + 15) >> 4
        gfx = planar_to_idx(data, p + g, ww, h, gp)
        msk = planar_to_idx(data, p + m, ww, h, 1) if mp else None
        sprites.append(dict(w=w, h=h, gp=gp, mp=mp, gofs=g, mofs=m, gfx=gfx, msk=msk))
    W = sum(ww16(s['w']) + 1 for s in sprites) - 1
    H = max(s['h'] for s in sprites)
    im = Image.new('P', (max(W, 1), H), 16)
    im.putpalette(pal_bytes(pal))
    x = 0
    layout = []
    for s in sprites:
        wpx = ww16(s['w'])
        for y in range(s['h']):
            for xx in range(wpx):
                gv = s['gfx'][y][xx]
                mv = 1 if s['msk'] is None else 1 - s['msk'][y][xx]
                im.putpixel((x + xx, y), _encode_px(gv, mv))
        layout.append(dict(x=x, w=s['w'], h=s['h'], gp=s['gp'], mp=s['mp']))
        x += wpx + 1
    im.save(png)
    return {'type': 'BSB', 'version': ver, 'sprites': layout}


def ww16(w):
    return ((w + 15) >> 4) << 4


def import_bsb(png, meta):
    im = Image.open(png)
    assert im.mode == 'P'
    cnt = len(meta['sprites'])
    head = struct.pack('>IHH', 0x4253424b, meta['version'], cnt)
    ptr_end = 8 + 4 * cnt
    blobs, ptrs = [], []
    pos = ptr_end
    for s in meta['sprites']:
        wpx = ww16(s['w'])
        gfx, msk = [], []
        for y in range(s['h']):
            gr, mr = [], []
            for xx in range(wpx):
                v = im.getpixel((s['x'] + xx, y))
                gr.append(v & 15)
                mr.append(0 if v < 16 else 1)
            gfx.append(gr)
            msk.append(mr)
        mbytes = idx_to_planar(msk, 1) if s['mp'] else b''
        gbytes = idx_to_planar(gfx, s['gp'])
        mofs = 16
        gofs = 16 + len(mbytes)
        if not s['mp']:
            mofs = gofs = 16
        blob = struct.pack('>IIHHHH', gofs, mofs, s['w'], s['h'], s['gp'], s['mp']) + mbytes + gbytes
        ptrs.append(pos)
        blobs.append(blob)
        pos += len(blob)
    return head + struct.pack('>%dI' % cnt, *ptrs) + b''.join(blobs)


# ---------------------------------------------------------------- GFX
def export_gfx(data, png, pal):
    ident, ver, w, h, planes, mflag = struct.unpack('>4sHHHBB', data[:12])
    ww = (w + 15) >> 4
    m = 1 if mflag else 0
    rows = planar_to_idx(data, 12, ww, h, planes + m)
    im = Image.new('P', (ww * 16, h))
    im.putpalette(pal_bytes(pal))
    im.putdata([_encode_px(v >> m, 1 - (v & 1) if m else 1) for r in rows for v in r])
    im.save(png)
    return {'type': 'GFX', 'version': ver, 'w': w, 'h': h, 'planes': planes, 'mask': mflag}


def import_gfx(png, meta):
    im = Image.open(png)
    m = 1 if meta['mask'] else 0
    ww = (meta['w'] + 15) >> 4
    rows = []
    for y in range(meta['h']):
        r = []
        for x in range(ww * 16):
            v = im.getpixel((x, y))
            g = v & 15
            opaque = v < 16
            r.append((g << m) | ((0 if opaque else 1) if m else 0))
        rows.append(r)
    return (struct.pack('>4sHHHBB', b'GFX ', meta['version'], meta['w'], meta['h'], meta['planes'], meta['mask'])
            + idx_to_planar(rows, meta['planes'] + m))


# ---------------------------------------------------------------- driver
def export_all(files_dir, out):
    os.makedirs(out, exist_ok=True)
    for f in sorted(os.listdir(files_dir)):
        src = os.path.join(files_dir, f)
        data = open(src, 'rb').read()
        ext = f.rsplit('.', 1)[-1] if '.' in f else ''
        png = os.path.join(out, f + '.png')
        meta = None
        if ext == 'PI1':
            meta = export_pi1(data, png)
        elif ext == 'BSB':
            meta = export_bsb(data, png, sprite_palette(files_dir, f))
        elif ext == 'GFX':
            meta = export_gfx(data, png, sprite_palette(files_dir, f))
        if meta:
            json.dump(meta, open(png[:-4] + '.json', 'w'), indent=1)
        else:
            shutil.copy(src, os.path.join(out, f))


def import_all(assets, orig_files, out):
    os.makedirs(out, exist_ok=True)
    for f in sorted(os.listdir(orig_files)):
        png = os.path.join(assets, f + '.png')
        js = os.path.join(assets, f + '.json')
        if os.path.exists(js):
            meta = json.load(open(js))
            data = {'PI1': import_pi1, 'BSB': import_bsb, 'GFX': import_gfx}[meta['type']](png, meta)
        else:
            data = open(os.path.join(assets, f), 'rb').read()
        open(os.path.join(out, f), 'wb').write(data)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'export':
        export_all(sys.argv[2], sys.argv[3])
    elif cmd == 'import':
        import_all(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'selftest':
        import tempfile, filecmp
        files = sys.argv[2]
        t = tempfile.mkdtemp()
        export_all(files, t + '/a')
        import_all(t + '/a', files, t + '/b')
        bad = [f for f in os.listdir(files) if open(files + '/' + f, 'rb').read() != open(t + '/b/' + f, 'rb').read()]
        print('selftest: %d files, %d differ %s' % (len(os.listdir(files)), len(bad), bad[:10]))
