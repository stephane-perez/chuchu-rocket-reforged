#!/usr/bin/env python3
"""Differential test: run the same routine of two builds (original / optimised)
in a 68000 emulator (Unicorn) on many inputs, and compare everything the
caller can observe: result registers, callee-saved registers d3-d7/a2-a6,
stack pointer, and the memory the routine writes.

  python tools/difftest.py            (needs vasmm68k_mot and `pip install unicorn`)

Each build is assembled with symbols, loaded at $10000 with its relocation
table applied, and each routine is located by its label."""
import os, sys, struct, random, subprocess, tempfile
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_READ
from unicorn.m68k_const import *

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from prg import PRG

BASE, RET, STACK = 0x10000, 0x8000, 0x7000
D = [UC_M68K_REG_D0 + i for i in range(8)]
A = [UC_M68K_REG_A0 + i for i in range(8)]


class Syms(dict):
    """Symbol names are truncated to 22 characters in the TOS (GST) symbol table."""
    def __getitem__(self, k):
        return dict.__getitem__(self, k[:22])


def build(defines):
    out = tempfile.mktemp(suffix='.prg')
    subprocess.run([os.environ.get('VASM', 'vasmm68k_mot'), '-Ftos', '-no-opt', '-m68000', '-tos-flags=6', '-quiet',
                    '-o', out, os.path.join(ROOT, 'src', 'chuchu.s')] + ['-D%s=1' % d for d in defines], check=True)
    raw = open(out, 'rb').read()
    p = PRG(raw)
    # DRI/GST symbol table (with extended names)
    st = raw[28 + p.tlen + p.dlen:28 + p.tlen + p.dlen + p.slen]
    syms, i = Syms(), 0
    while i < len(st):
        name = st[i:i + 8]
        typ, val = struct.unpack('>HI', st[i + 8:i + 14])
        i += 14
        if typ & 0x48 == 0x48:
            name += st[i:i + 14]
            i += 14
        syms[name.rstrip(b'\0').decode('latin1')] = val + (p.tlen if typ & 0x0400 else 0) + \
            (p.tlen + p.dlen if typ & 0x0100 else 0)
    img = bytearray(p.image) + bytes(p.blen)
    for r in p.relocs:
        v = struct.unpack('>I', img[r:r + 4])[0]
        img[r:r + 4] = struct.pack('>I', v + BASE)
    return img, syms


class Machine:
    def __init__(self, img):
        self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        self.uc.mem_map(0, 0x10000)
        self.size = (len(img) + 0xffff) & ~0xffff
        self.uc.mem_map(BASE, self.size + 0x10000)
        self.img = bytes(img)

    def reset(self):
        self.uc.mem_write(BASE, self.img)
        self.uc.mem_write(0, bytes(0x10000))

    def call(self, addr, regs, mem=(), reset=True):
        uc = self.uc
        if reset:
            self.reset()
        for a, b in mem:
            uc.mem_write(a, b)
        for i in range(8):
            uc.reg_write(D[i], regs.get('d%d' % i, 0x11110000 + i))
        for i in range(7):
            uc.reg_write(A[i], regs.get('a%d' % i, 0x22220000 + i))
        uc.mem_write(STACK, struct.pack('>I', RET))
        uc.reg_write(UC_M68K_REG_A7, STACK)
        uc.emu_start(BASE + addr, RET, count=200000)
        return {**{'d%d' % i: uc.reg_read(D[i]) for i in range(8)},
                **{'a%d' % i: uc.reg_read(A[i]) for i in range(8)}}


SAVED = ['d3', 'd4', 'd5', 'd6', 'd7', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7']


def test(name, gen, n, observe):
    fails = 0
    for k in range(n):
        regs, mem = gen(k)
        outs = []
        for m, s in ((M0, S0), (M1, S1)):
            r = m.call(s[name], regs, mem)
            outs.append((tuple(r[x] for x in observe + SAVED), m.uc.mem_read(0x4000, 16)))
        if outs[0] != outs[1]:
            fails += 1
            if fails <= 3:
                print('   MISMATCH', name, regs, outs)
    print('%-8s %6d cases : %s' % (name, n, 'IDENTICAL' if not fails else '%d differences' % fails))
    return fails == 0


class Blitter:
    """Minimal STE blitter model (HOP=source, OP=3 copy, any increments/masks),
    run when the CPU reads the control register ($3c) while BUSY is set:
    the copy completes instantly and BUSY reads back as 0."""
    def __init__(self, uc):
        self.uc = uc
        self.blits = 0
        for base in (0xff8000, 0xffff8000):
            uc.mem_map(base, 0x1000)
            uc.hook_add(UC_HOOK_MEM_READ, self.hook, begin=base + 0xa3c, end=base + 0xa3c)

    def r16(self, a):
        return struct.unpack('>H', bytes(self.uc.mem_read(a, 2)))[0]

    def r32(self, a):
        return struct.unpack('>I', bytes(self.uc.mem_read(a, 4)))[0]

    def hook(self, uc, access, address, size, value, user):
        io = address - 0x3c
        ctrl = uc.mem_read(address, 1)[0]
        if ctrl & 0x80:
            ycount = self.r16(io + 0x38)
            if ycount:
                self.run(io)
            uc.mem_write(address, bytes([ctrl & 0x7f]))

    def run(self, io):
        s16 = lambda v: v - 0x10000 if v & 0x8000 else v
        sxi, syi, src = s16(self.r16(io + 0x20)), s16(self.r16(io + 0x22)), self.r32(io + 0x24) & 0xffffff
        m1, m2, m3 = self.r16(io + 0x28), self.r16(io + 0x2a), self.r16(io + 0x2c)
        dxi, dyi, dst = s16(self.r16(io + 0x2e)), s16(self.r16(io + 0x30)), self.r32(io + 0x32) & 0xffffff
        xc, yc = self.r16(io + 0x36), self.r16(io + 0x38)
        hop, op, skew = self.uc.mem_read(io + 0x3a, 1)[0], self.uc.mem_read(io + 0x3b, 1)[0], self.uc.mem_read(io + 0x3d, 1)[0]
        assert hop == 2 and op == 3 and skew == 0, (hop, op, skew)
        for y in range(yc):
            for x in range(xc):
                w = self.r16(src)
                m = m1 if x == 0 else (m3 if x == xc - 1 else m2)
                old = self.r16(dst)
                self.uc.mem_write(dst, struct.pack('>H', (w & m) | (old & ~m & 0xffff)))
                last = x == xc - 1
                src += syi if last else sxi
                dst += dyi if last else dxi
        self.uc.mem_write(io + 0x24, struct.pack('>I', src))
        self.uc.mem_write(io + 0x32, struct.pack('>I', dst))
        self.uc.mem_write(io + 0x38, b'\0\0')
        self.blits += 1


def blit_restore(ncases=400):
    """Board_RestoreDirtyCells / Board_RestoreDirtyBorder (F_16604 / F_16706, background restore): original CPU copy vs OPT_BLIT
    (blitter present). Random masks and random source/destination boards;
    compares the whole destination board, the mask words and every register."""
    SRC, DST, MASK = 0x100000, 0x120000, 0x4000
    for m in (M0, M1):
        if not hasattr(m, 'blitter'):
            m.uc.mem_map(SRC, 0x40000)
            m.blitter = Blitter(m.uc)
    rnd = random.Random(11)
    ok = True
    for name, nrows, first in (('Board_RestoreDirtyCells', 9, 8), ('Board_RestoreDirtyBorder', 10, 0)):
        bad = 0
        tiles = 0
        for k in range(ncases):
            dens = [0.0, 1.0, 0.1, 0.3, 0.6][k % 5]
            masks = [sum(1 << b for b in range(16) if rnd.random() < dens) if k % 7 else rnd.getrandbits(16)
                     for _ in range(nrows)]
            board_s = bytes(rnd.getrandbits(8) for _ in range(0xa00 * 10 + 0x100))
            board_d = bytes(rnd.getrandbits(8) for _ in range(0xa00 * 10 + 0x100))
            res = []
            for mach, syms in ((M0, S0), (M1, S1)):
                mach.reset()
                mach.uc.mem_write(SRC, board_s)
                mach.uc.mem_write(DST, board_d)
                mach.uc.mem_write(MASK, struct.pack('>%dH' % nrows, *masks))
                mach.uc.mem_write(BASE + syms['gSystemBLT'], b'\0\1')      # blitter present
                mach.uc.mem_write(STACK + 4, struct.pack('>I', DST + first))
                n0 = mach.blitter.blits
                r = mach.call(syms[name], {'a0': MASK, 'a1': SRC + first}, reset=False)
                if mach is M1:
                    tiles += mach.blitter.blits - n0
                res.append((bytes(mach.uc.mem_read(DST, 0xa00 * 10 + 0x100)),
                            bytes(mach.uc.mem_read(MASK, 2 * nrows)),
                            tuple(r['d%d' % i] for i in range(8)) + tuple(r['a%d' % i] for i in range(8))))
            if res[0] != res[1]:
                bad += 1
                if bad <= 2:
                    print('   MISMATCH', name, 'masks', [hex(x) for x in masks],
                          'board' if res[0][0] != res[1][0] else '', 'masks' if res[0][1] != res[1][1] else '',
                          'regs' if res[0][2] != res[1][2] else '')
        print('%-8s %6d cases (%d blitter copies) : %s' % (name, ncases, tiles, 'IDENTICAL' if not bad else '%d differences' % bad))
        ok &= bad == 0
    return ok


def mixer_sequence(ncalls=400):
    """AudioMixer_MixChunk (F_01da4, DMA mixer) driven like its caller L_01cca: 8 KB ring buffer,
    calls split at the wrap, voices silent most of the time, sometimes active
    with random samples and panning tables. Ring compared after every call."""
    RING, SIL, SMP = 0x9000, 0xc000, 0xd000
    rnd = random.Random(7)
    samples = bytes(rnd.randrange(256) for _ in range(0x2000))
    def table(v):
        return bytes(((((s ^ 0x80) - 0x80) * v) >> 8) & 0xff for s in range(256))
    for m in (M0, M1):
        m.reset()
        m.uc.mem_write(RING, bytes(rnd.randrange(256) for _ in range(0x2000)) if m is M0 else bytes(0x2000))
        m.uc.mem_write(SMP, samples)
    # both rings start from the same (garbage) content
    M1.uc.mem_write(RING, bytes(M0.uc.mem_read(RING, 0x2000)))
    tab_a = BASE + ((len(img0) + 0xffff) & ~0xffff)
    tab_b = BASE + ((len(img1) + 0xffff) & ~0xffff)
    pos, bad, active_calls = 0, 0, 0
    for k in range(ncalls):
        act0 = rnd.random() < 0.15
        act1 = rnd.random() < 0.08
        v0, v1 = rnd.randrange(256), rnd.randrange(256)
        length = rnd.randrange(0, 0x2000 // 8) * 8
        p0 = SMP + rnd.randrange(0, 0x1000) if act0 else SIL
        p1 = SMP + rnd.randrange(0, 0x1000) if act1 else SIL
        active_calls += act0 or act1
        parts = [(pos, min(length, 0x2000 - pos))]
        if pos + length > 0x2000:
            parts.append((0, pos + length - 0x2000))
        for m, s, tb in ((M0, S0, tab_a), (M1, S1, tab_b)):
            fl = s['gAudioMixerVoices'] + BASE
            m.uc.mem_write(fl + 0xf, bytes([act0]))
            m.uc.mem_write(fl + 0x1f, bytes([act1]))
            m.uc.mem_write(tb, table(v0) + table(v1))
            a0, a1 = p0, p1
            for (at, n) in parts:
                r = m.call(s['AudioMixer_MixChunk'], {'d0': n, 'a0': a0, 'a1': a1, 'a2': RING + at,
                                          'a3': tb, 'a5': tb + 256}, reset=False)
                a0, a1 = r['a0'], r['a1']
        pos = (pos + length) % 0x2000
        if bytes(M0.uc.mem_read(RING, 0x2000)) != bytes(M1.uc.mem_read(RING, 0x2000)):
            bad += 1
    print('AudioMixer_MixChunk  %6d calls (%d with an active voice) : buffer %s' % (
        ncalls, active_calls, 'IDENTICAL after every call' if not bad else 'DIFFERENT %d times' % bad))
    return bad == 0


if __name__ == '__main__':
    img0, S0 = build([])
    img1, S1 = build(['OPTIM'])
    M0, M1 = Machine(img0), Machine(img1)
    random.seed(1)
    ok = True

    # Time_ToTicks (F_0173a) : a0 -> {h,m,s,f}, returns ticks in d0
    def g173(k):
        b = bytes([k & 0xff, (k >> 8) & 0xff, random.randrange(256), random.randrange(256)]) if k < 65536 \
            else bytes(random.randrange(256) for _ in range(4))
        return {'a0': 0x4000}, [(0x4000, b)]
    ok &= test('Time_ToTicks', g173, 70000, ['d0'])

    # Time_FromTicks (F_0178c) : d0 ticks -> {h,m,s,f} at a0, d0 = seconds
    edges = [0, 1, 199, 200, 11999, 12000, 719999, 720000, 36000, 0x7fffffff, 0x80000000, 0xffffffff,
             0xfffffff0, 720000 * 255, 720000 * 256, 720000 * 5965, 720000 * 5966 - 1]
    def g178(k):
        if k < len(edges):
            v = edges[k]
        elif k < 50000:
            v = random.randrange(0, 1000000)            # durees realistes
        elif k < 60000:
            v = (-random.randrange(1, 1000000)) & 0xffffffff   # durees negatives
        else:
            v = random.getrandbits(32)
        return {'a0': 0x4000, 'd0': v}, []
    ok &= test('Time_FromTicks', g178, 80000, ['d0'])
    ok &= mixer_sequence()
    ok &= blit_restore()
    print('RESULT :', 'OK' if ok else 'FAILED')
    sys.exit(0 if ok else 1)
