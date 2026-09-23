"""Pack-Ice 2.40 depacker - transcription of the 68000 routine embedded
in CHUCHU.TOS (stub tables at text+$162: direkt_tab/length_tab/more_offset).
Usage: unice.py <file> <offset_of_ICE!> <out>"""
import sys, struct

DIREKT = [(0x7fff, 0x000e), (0x00ff, 0x0007), (0x0007, 0x0002), (0x0003, 0x0001), (0x0003, 0x0001)]
DCOUNT = [270 - 1, 15 - 1, 8 - 1, 5 - 1, 2 - 1]
LEN_BITS = [9, 1, 0, -1, -1]
LEN_BASE = [8, 4, 2, 1, 0]
OFF_BITS = [11, 4, 7, 0]
OFF_BASE = {-1: 0x011f, 0: -1, 1: 0x001f}

def s16(v):
    v &= 0xffff
    return v - 0x10000 if v & 0x8000 else v

def unice(buf):
    assert buf[:4] == b'ICE!'
    plen, ulen = struct.unpack('>II', buf[4:12])
    a5 = plen                      # read pointer (predecrement)
    out = bytearray(ulen)
    a6 = ulen                      # write pointer (predecrement)
    st = {'d7': 0, 'a5': a5}

    def rd():
        st['a5'] -= 1
        return buf[st['a5']]

    def get1():
        r = st['d7'] * 2
        c = r >> 8
        st['d7'] = r & 0xff
        if st['d7']:
            return c
        r = rd() * 2 + c
        c = r >> 8
        st['d7'] = r & 0xff
        return c

    def getbits(d0):               # reads d0+1 bits
        d1 = 0
        for _ in range(d0 + 1):
            d1 = ((d1 << 1) | get1()) & 0xffff
        return d1

    st['d7'] = rd()
    while True:
        # normal_bytes
        if get1():
            d1 = 0
            if get1():
                for i in range(5):         # d3 = 4..0, a1 walks down the table
                    idx = 4 - i
                    mask, nb = DIREKT[idx]
                    d1 = getbits(nb)
                    if d1 != mask:
                        break
                d1 += DCOUNT[idx]
            for _ in range(d1 + 1):
                a6 -= 1
                out[a6] = rd()
        if not a6 > 0:
            break
        # strings
        d2 = 3
        while True:
            if not get1():
                break
            d2 -= 1
            if d2 == -1:
                break
        d1 = 0
        nb = LEN_BITS[1 + d2]
        if nb >= 0:
            d1 = getbits(nb)
        d4 = (LEN_BASE[1 + d2] + d1) & 0xffff
        if d4 == 0:
            d0, base = 5, -1
            if get1():
                d0, base = 8, 0x3f
            d1 = s16(getbits(d0) + base)
        else:
            d2 = 1
            while True:
                if not get1():
                    break
                d2 -= 1
                if d2 == -1:
                    break
            d1 = getbits(OFF_BITS[1 + d2])
            d1 = s16(d1 + OFF_BASE[d2])
            if d1 < 0:
                d1 = s16(d1 - d4)
        a1 = a6 + 2 + s16(d4) + d1
        for _ in range(d4 + 2):
            a1 -= 1
            a6 -= 1
            out[a6] = out[a1]
    picture = get1()
    info = dict(packed=plen, unpacked=ulen, left=st['a5'] - 12, picture=picture)
    if picture:
        # interleaved-plane back-conversion on the last 32000 bytes
        a3 = ulen
        d = [0, 0, 0, 0]
        for _ in range(0x0f9f + 1):
            for _ in range(4):
                a3 -= 2
                d4 = struct.unpack('>H', out[a3:a3 + 2])[0]
                for _ in range(4):
                    for k in range(4):
                        d[k] = ((d[k] << 1) | (d4 >> 15)) & 0xffff
                        d4 = (d4 << 1) & 0xffff
            out[a3:a3 + 8] = struct.pack('>4H', *d)
    return bytes(out), info

if __name__ == '__main__':
    data = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[2], 0)
    res, info = unice(data[off:])
    open(sys.argv[3], 'wb').write(res)
    print(info)
