"""Frame-time statistics during gameplay from fpslog output.
Gameplay frame = displayed frame preceded (since previous frame) by a
call to the arrow renderer Arrows_Draw (F_156ac, only called in game)."""
import sys, collections
def stats(path):
    ev = [int(l) for l in open(path) if l.strip()]
    frames = []          # (vbl, gameplay?)
    g = False
    for v in ev:
        if v >= 1000000: g = True
        else:
            frames.append((v, g)); g = False
    iv = collections.Counter(); games = 0; gvbl = 0; gfr = 0
    prev = None
    for (v, gp) in frames:
        if gp and prev is not None and prev[1]:
            d = v - prev[0]
            if d <= 12:
                iv[d] += 1; gvbl += d; gfr += 1
        prev = (v, gp)
    return iv, gfr, gvbl
for p in sys.argv[1:]:
    iv, n, vb = stats(p)
    print('%-12s gameplay frames %5d over %6d VBL : %.1f fps (mean %.2f VBL/frame)' % (p, n, vb, 50 * n / vb, vb / n))
    print('             distribution (VBL/frame): ' + '  '.join('%d:%4.1f%%' % (k, 100 * iv[k] / n) for k in sorted(iv)))
