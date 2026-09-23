"""Demo graphics mod: add a banner to the title screen, drawn with the
game's own 8x8 font (FONTMID.IMG, chars from ' ' at 8 bytes each)."""
from PIL import Image
import sys
root = sys.argv[1] if len(sys.argv) > 1 else '.'
font = open(root + '/assets/FONTMID.IMG', 'rb').read()
im = Image.open(root + '/assets/TITLE.PI1.png')

def text(x, y, s, fg, shadow):
    for i, ch in enumerate(s):
        g = font[(ord(ch) - 32) * 8:(ord(ch) - 32) * 8 + 8]
        for yy, row in enumerate(g):
            for xx in range(8):
                if row & (0x80 >> xx):
                    im.putpixel((x + i * 8 + xx + 1, y + yy + 1), shadow)
                    im.putpixel((x + i * 8 + xx, y + yy), fg)

msg = 'ST REFORGED 2026'
x0, y0 = 8, 184
for y in range(y0 - 3, y0 + 11):
    for x in range(x0 - 4, x0 + len(msg) * 8 + 5):
        im.putpixel((x, y), 2)            # dark blue box (palette index 2)
text(x0, y0, msg, 9, 7)                    # yellow text (9), dark shadow (7)
im.save(root + '/assets/TITLE.PI1.png')
print('title banner added')
