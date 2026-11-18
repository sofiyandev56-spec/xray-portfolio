"""
Renders the name written in the intro, as ink: white letters on transparency,
the same format as public/hero/signature.png.

  public/hero/name.png

The script is Monsieur La Doulaise (Google Fonts, SIL Open Font License), chosen
for its looping capitals and thick-and-hairline contrast. It comes from the
@fontsource/monsieur-la-doulaise dev dependency, so run `npm install` first.

Then trace its pen strokes for the stroke-by-stroke animation:

  python3 tools/signature/render_name.py
  python3 tools/signature/vectorize.py --src public/hero/name.png \\
      --out src/data/name-strokes.json --mode name --scale 1 --preview
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / 'node_modules' / '@fontsource' / 'monsieur-la-doulaise' / 'files' / 'monsieur-la-doulaise-latin-400-normal.woff'
OUT = ROOT / 'public' / 'hero' / 'name.png'
TEXT = 'Sofiyan Shaikh'
SIZE = 300  # large enough that the hairlines survive tracing
PAD = 24

font = ImageFont.truetype(str(FONT), SIZE)
left, top, right, bottom = font.getbbox(TEXT)
w, h = right - left + PAD * 2, bottom - top + PAD * 2

ink = Image.new('L', (w, h), 0)
ImageDraw.Draw(ink).text((PAD - left, PAD - top), TEXT, font=font, fill=255)

out = Image.new('RGBA', (w, h), (255, 255, 255, 0))
out.putalpha(ink)
out.save(OUT, optimize=True)
print(f'wrote {OUT.relative_to(ROOT)} ({w} x {h})')
