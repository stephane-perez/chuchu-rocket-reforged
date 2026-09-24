"""Bandeau sur l'ecran titre, ecrit avec la police 8x8 du jeu (FONTMID.IMG).

  python mods/title/make.py [texte] [dossier_sortie]
  defaut : "AI REFORGED 2026" -> mods/reforged/TITLE.PI1.png (+ .json)
Lit toujours l'image d'origine dans assets/, qui n'est pas modifie."""
from PIL import Image
import sys, os, shutil
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
msg = sys.argv[1] if len(sys.argv) > 1 else 'AI REFORGED 2026'
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, 'mods', 'reforged')
font = open(os.path.join(root, 'assets', 'FONTMID.IMG'), 'rb').read()
im = Image.open(os.path.join(root, 'assets', 'TITLE.PI1.png'))

def text(x, y, s, fg, shadow):
    for i, ch in enumerate(s):
        g = font[(ord(ch) - 32) * 8:(ord(ch) - 32) * 8 + 8]
        for yy, row in enumerate(g):
            for xx in range(8):
                if row & (0x80 >> xx):
                    im.putpixel((x + i * 8 + xx + 1, y + yy + 1), shadow)
                    im.putpixel((x + i * 8 + xx, y + yy), fg)

x0, y0 = 8, 184
for y in range(y0 - 3, y0 + 11):
    for x in range(x0 - 4, x0 + len(msg) * 8 + 5):
        im.putpixel((x, y), 2)            # cadre bleu fonce (index 2 de la palette)
text(x0, y0, msg, 9, 7)                    # texte jaune (9), ombre sombre (7)
os.makedirs(out, exist_ok=True)
im.save(os.path.join(out, 'TITLE.PI1.png'))
shutil.copy(os.path.join(root, 'assets', 'TITLE.PI1.json'), os.path.join(out, 'TITLE.PI1.json'))
print('bandeau "%s" -> %s' % (msg, os.path.relpath(out, root)))
