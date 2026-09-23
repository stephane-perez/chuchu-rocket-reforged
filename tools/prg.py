"""GEMDOS PRG parsing helpers."""
import struct

class PRG:
    def __init__(self, data):
        self.raw = data
        (self.magic, self.tlen, self.dlen, self.blen, self.slen,
         self.res1, self.flags, self.absflag) = struct.unpack('>HIIIIIIH', data[:28])
        assert self.magic == 0x601a
        o = 28
        self.text = data[o:o + self.tlen]; o += self.tlen
        self.data = data[o:o + self.dlen]; o += self.dlen
        self.sym = data[o:o + self.slen]; o += self.slen
        self.image = self.text + self.data
        self.relocs = []
        self.reloc_raw_start = o
        if self.absflag == 0:
            first = struct.unpack('>I', data[o:o + 4])[0]; o += 4
            if first:
                pos = first
                self.relocs.append(pos)
                while True:
                    b = data[o]; o += 1
                    if b == 0: break
                    if b == 1: pos += 254; continue
                    pos += b
                    self.relocs.append(pos)
        self.reloc_end = o
        self.trailing = data[o:]

    def long(self, off):
        return struct.unpack('>I', self.image[off:off + 4])[0]
