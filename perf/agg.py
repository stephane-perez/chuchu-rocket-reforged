"""Aggregate a Hatari profile save by function (TEXT symbols) and memory region."""
import sys, re, bisect, collections
prof, sym = sys.argv[1], sys.argv[2]
top = int(sys.argv[3]) if len(sys.argv) > 3 else 40
lines = open(prof).read().split('\n')
text = None
for l in lines:
    m = re.match(r'PROGRAM_TEXT:\s+0x([0-9a-f]+)-0x([0-9a-f]+)', l)
    if m: text = (int(m.group(1), 16), int(m.group(2), 16))
syms = sorted((int(l.split()[0], 16) + text[0], l.split()[2]) for l in open(sym) if l.strip())
addrs = [s[0] for s in syms]
per = collections.Counter(); cnt = collections.Counter(); region = collections.Counter()
tot = 0
for l in lines:
    m = re.match(r'^([0-9a-f]{8}) .*\((\d+), (\d+), \d+, \d+\)$', l)
    if not m: continue
    a, n, c = int(m.group(1), 16), int(m.group(2)), int(m.group(3))
    tot += c
    if text[0] <= a < text[1]:
        i = bisect.bisect_right(addrs, a) - 1
        f = syms[i][1] if i >= 0 else '?'
        per[f] += c; cnt[f] += n; region['game code (TEXT)'] += c
    elif a < 0x800: region['low RAM $200-$800 (SID timer IRQs)'] += c
    elif a >= 0xe00000: region['TOS ROM'] += c
    else: region['other RAM (SNDREP player, ...)'] += c
print('total cycles %d (%.2f s at 8 MHz)' % (tot, tot / 8021247))
for r, c in region.most_common(): print('  %-40s %5.1f%%' % (r, 100 * c / tot))
print('top functions:')
for f, c in per.most_common(top):
    print('  %-24s %5.1f%%  %10d cycles %9d instr' % (f, 100 * c / tot, c, cnt[f]))
