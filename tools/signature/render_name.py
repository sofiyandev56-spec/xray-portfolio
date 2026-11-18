"""
Renders the name for the intro's autograph, so its pen strokes can be traced.

  tools/signature/name-ink.png   (an intermediate; not shipped)

The site never shows this image. tools/signature/vectorize.py traces the centre
line of every stroke in it, and the intro draws those lines as one bold, even
marker stroke that grows letter by letter, the way the autograph on
landonorris.com is drawn.

The script is Whisper (Google Fonts, SIL Open Font License): slanted, quick and
looping like a real signature, but still readable. It comes from the
@fontsource/whisper dev dependency, so run `npm install` first.

  python3 tools/signature/render_name.py
  python3 tools/signature/vectorize.py --src tools/signature/name-ink.png \\
      --out src/data/name-strokes.json --mode name --scale 1 --preview
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / 'node_modules' / '@fontsource' / 'whisper' / 'files' / 'whisper-latin-400-normal.woff'
OUT = ROOT / 'tools' / 'signature' / 'name-ink.png'
TEXT = 'Sofiyan Shaikh'
SIZE = 300  # large enough for clean centre lines
PAD = 30
SWOOSH_ROOM = 0.32  # extra space below the letters for the closing underline

font = ImageFont.truetype(str(FONT), SIZE)
left, top, right, bottom = font.getbbox(TEXT)
w = right - left + PAD * 2
h = bottom - top + PAD * 2
h += round(h * SWOOSH_ROOM)

ink = Image.new('L', (w, h), 0)
ImageDraw.Draw(ink).text((PAD - left, PAD - top), TEXT, font=font, fill=255)

out = Image.new('RGBA', (w, h), (255, 255, 255, 0))
out.putalpha(ink)
out.save(OUT, optimize=True)
print(f'wrote {OUT.relative_to(ROOT)} ({w} x {h})')
