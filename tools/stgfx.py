"""Atari ST planar graphics <-> images (Degas PI1, GodLib BSB sprite blocks, GFX)."""
import struct
from PIL import Image

def st_pal(words):
    """ST/STE palette words -> list of RGB (STE 4-bit, low bit in bit 3)."""
    out = []
    for w in words:
        c = []
        for sh in (8, 4, 0):
            n = (w >> sh) & 0xf
            v = ((n & 7) << 1) | (n >> 3)
            c.append(v * 17)
        out.append(tuple(c))
    return out

def planar_to_idx(buf, off, wwords, h, planes, interleaved=True):
    """Interleaved-bitplane rows (ST screen layout) -> 2D list of indices."""
    rows = []
    for y in range(h):
        row = []
        for x16 in range(wwords):
            base = off + (y * wwords + x16) * planes * 2
            ws = struct.unpack('>%dH' % planes, buf[base:base + planes * 2])
            for b in range(15, -1, -1):
                v = 0
                for p in range(planes):
                    v |= ((ws[p] >> b) & 1) << p
                row.append(v)
        rows.append(row)
    return rows

def idx_to_planar(rows, planes):
    out = bytearray()
    for row in rows:
        for x16 in range(0, len(row), 16):
            ws = [0] * planes
            for i, v in enumerate(row[x16:x16 + 16]):
                for p in range(planes):
                    ws[p] |= ((v >> p) & 1) << (15 - i)
            out += struct.pack('>%dH' % planes, *ws)
    return bytes(out)

def rows_to_img(rows, pal, mask=None):
    h, w = len(rows), len(rows[0])
    im = Image.new('RGBA', (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b = pal[rows[y][x]]
            a = 255 if (mask is None or mask[y][x]) else 0
            px[x, y] = (r, g, b, a)
    return im

def pi1_to_png(data, path):
    res = struct.unpack('>H', data[:2])[0]
    assert res == 0
    pal = st_pal(struct.unpack('>16H', data[2:34]))
    rows = planar_to_idx(data, 34, 20, 200, 4)
    rows_to_img(rows, pal).save(path)
    return pal

def bsb_sprites(data):
    ident, ver, cnt = struct.unpack('>IHH', data[:8])
    assert ident == 0x4253424b
    ptrs = struct.unpack('>%dI' % cnt, data[8:8 + 4 * cnt])
    out = []
    for p in ptrs:
        g, m, w, h, gp, mp = struct.unpack('>IIHHHH', data[p:p + 16])
        ww = (w + 15) >> 4
        gfx = planar_to_idx(data, p + g, ww, h, gp)
        msk = None
        if mp:
            msk = [[1 - v for v in r] for r in planar_to_idx(data, p + m, ww, h, 1)]
        out.append(dict(w=w, h=h, gp=gp, mp=mp, gfx=gfx, mask=msk))
    return out

def gfx_image(data):
    """'GFX ' : U16 version, U16 width, U16 height, U8 planes, U8 maskflag.
    Then per line, per 16-pixel group: [mask word] + planes words.
    Mask bit 1 = transparent (checked visually on ATARI.GFX)."""
    ident, ver, w, h, planes, mflag = struct.unpack('>4sHHHBB', data[:12])
    assert ident == b'GFX '
    ww = (w + 15) >> 4
    m = 1 if mflag else 0
    rows = planar_to_idx(data, 12, ww, h, planes + m)
    gfx = [[v >> m for v in r] for r in rows]
    msk = [[1 - (v & 1) for v in r] for r in rows] if m else None
    return dict(w=w, h=h, planes=planes, gfx=gfx, mask=msk)
