"""Atari ST reference names: hardware registers, system variables, traps."""
HW = {
    0x70: 'VBL vector', 0x68: 'HBL vector', 0x110: 'MFP Timer D vector', 0x114: 'MFP Timer C vector',
    0x118: 'MFP ACIA (IKBD/MIDI) vector', 0x120: 'MFP Timer B vector', 0x134: 'MFP Timer A vector',
    0x84: 'TRAP #1 (GEMDOS) vector', 0xb4: 'TRAP #13 (BIOS) vector', 0xb8: 'TRAP #14 (XBIOS) vector',
    0x42e: 'phystop', 0x436: '_memtop', 0x44c: 'sshiftmd', 0x44e: '_v_bas_ad', 0x452: 'vblsem',
    0x454: 'nvbls', 0x456: '_vblqueue', 0x462: '_vbclock', 0x466: '_frclock', 0x484: 'conterm',
    0x4ba: '_hz_200', 0x4f2: '_sysbase', 0x5a0: '_p_cookies', 0x426: 'resvalid', 0x42a: 'resvector',
    0xff8001: 'MMU memory config', 0xff8201: 'video base high', 0xff8203: 'video base mid',
    0xff820d: 'video base low (STE)', 0xff8205: 'video counter high', 0xff8207: 'video counter mid',
    0xff8209: 'video counter low', 0xff820a: 'sync mode', 0xff820e: 'line offset (STE)',
    0xff820f: 'line offset (STE)', 0xff8240: 'palette 0', 0xff8260: 'shifter resolution',
    0xff8264: 'hscroll (STE, no prefetch)', 0xff8265: 'hscroll (STE)', 0xff8282: 'Falcon/Videl',
    0xff8800: 'YM2149 select/read', 0xff8802: 'YM2149 write',
    0xff8900: 'DMA sound control (STE)', 0xff8901: 'DMA sound control (STE)', 0xff8920: 'DMA sound mode (STE)',
    0xff8a00: 'Blitter halftone RAM', 0xff8a20: 'Blitter src X inc', 0xff8a3c: 'Blitter control',
    0xff9200: 'STE joypad/fire buttons', 0xff9202: 'STE joypad directions',
    0xfffa01: 'MFP GPIP', 0xfffa03: 'MFP AER', 0xfffa05: 'MFP DDR', 0xfffa07: 'MFP IERA',
    0xfffa09: 'MFP IERB', 0xfffa0b: 'MFP IPRA', 0xfffa0d: 'MFP IPRB', 0xfffa0f: 'MFP ISRA',
    0xfffa11: 'MFP ISRB', 0xfffa13: 'MFP IMRA', 0xfffa15: 'MFP IMRB', 0xfffa17: 'MFP VR',
    0xfffa19: 'MFP TACR', 0xfffa1b: 'MFP TBCR', 0xfffa1d: 'MFP TCDCR', 0xfffa1f: 'MFP TADR',
    0xfffa21: 'MFP TBDR', 0xfffa23: 'MFP TCDR', 0xfffa25: 'MFP TDDR',
    0xfffc00: 'ACIA IKBD control', 0xfffc02: 'ACIA IKBD data',
}
GEMDOS = {0x00: 'Pterm0', 0x01: 'Cconin', 0x02: 'Cconout', 0x07: "Crawcin", 0x08: "Cnecin", 0x09: 'Cconws', 0x0b: 'Cconis',
          0x0e: 'Dsetdrv', 0x19: 'Dgetdrv', 0x1a: 'Fsetdta', 0x20: 'Super', 0x2a: 'Tgetdate', 0x2c: 'Tgettime',
          0x2f: 'Fgetdta', 0x30: 'Sversion', 0x31: 'Ptermres', 0x36: 'Dfree', 0x39: 'Dcreate', 0x3a: 'Ddelete',
          0x3b: 'Dsetpath', 0x3c: 'Fcreate', 0x3d: 'Fopen', 0x3e: 'Fclose', 0x3f: 'Fread', 0x40: 'Fwrite',
          0x41: 'Fdelete', 0x42: 'Fseek', 0x43: 'Fattrib', 0x44: 'Mxalloc', 0x47: 'Dgetpath', 0x48: 'Malloc',
          0x49: 'Mfree', 0x4a: 'Mshrink', 0x4b: 'Pexec', 0x4c: 'Pterm', 0x4e: 'Fsfirst', 0x4f: 'Fsnext',
          0x56: 'Frename', 0x57: 'Fdatime'}
BIOS = {0x00: 'Getmpb', 0x01: 'Bconstat', 0x02: 'Bconin', 0x03: 'Bconout', 0x04: 'Rwabs', 0x05: 'Setexc',
        0x06: 'Tickcal', 0x07: 'Getbpb', 0x08: 'Bcostat', 0x09: 'Mediach', 0x0a: 'Drvmap', 0x0b: 'Kbshift'}
XBIOS = {0x00: 'Initmous', 0x02: 'Physbase', 0x03: 'Logbase', 0x04: 'Getrez', 0x05: 'Setscreen',
         0x06: 'Setpalette', 0x07: 'Setcolor', 0x0e: 'Iorec', 0x10: 'Keytbl', 0x11: 'Random',
         0x15: 'Cursconf', 0x16: 'Settime', 0x17: 'Gettime', 0x19: 'Ikbdws', 0x1a: 'Jdisint', 0x1b: 'Jenabint',
         0x1c: 'Giaccess', 0x1d: 'Offgibit', 0x1e: 'Ongibit', 0x1f: 'Xbtimer', 0x20: 'Dosound',
         0x22: 'Kbdvbase', 0x25: 'Vsync', 0x26: 'Supexec', 0x40: 'Blitmode', 0x58: 'VsetMode', 0x59: 'mon_type',
         0x5a: 'VsetSync', 0x5b: 'VgetSize', 0x80: 'Locksnd', 0x81: 'Unlocksnd', 0x82: 'Soundcmd',
         0x83: 'Setbuffer', 0x84: 'Setmode', 0x86: 'Setinterrupt', 0x88: 'Buffoper', 0x8b: 'Devconnect'}
TRAPS = {1: ('GEMDOS', GEMDOS), 13: ('BIOS', BIOS), 14: ('XBIOS', XBIOS)}


def hw_name(addr):
    a = addr & 0xffffff
    if a in HW:
        return HW[a]
    if 0xff8240 <= a < 0xff8260:
        return 'palette %d' % ((a - 0xff8240) // 2)
    if 0xff8a00 <= a < 0xff8a40:
        return 'Blitter'
    return None
