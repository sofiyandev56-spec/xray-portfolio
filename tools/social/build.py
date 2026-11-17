"""
Builds the icons and the link-preview image from the hero assets:

  public/apple-touch-icon.png  180 x 180, the same mark as public/favicon.svg
  public/og-image.jpg          1200 x 630, shown when the site is shared: the photo
                               on the left, the x-ray on the right, split by the
                               same marigold edge the cursor draws

Run from the project root after rebuilding the x-ray (needs Pillow and NumPy):

  python3 tools/social/build.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'public'
PAPER, LINE, BLUE, ACCENT = (232, 236, 241), (159, 178, 214), (20, 51, 122), (255, 180, 0)


def grid(size, step, colour, alpha):
    layer = Image.new('RGBA', size, colour + (0,))
    d = ImageDraw.Draw(layer)
    for x in range(0, size[0], step):
        d.line([(x, 0), (x, size[1])], fill=colour + (alpha,), width=1)
    for y in range(0, size[1], step):
        d.line([(0, y), (size[0], y)], fill=colour + (alpha,), width=1)
    return layer


def icon():
    n = 180 * 4
    im = Image.new('RGBA', (n, n), BLUE + (255,))
    im.alpha_composite(grid((n, n), n // 4, LINE, 90))
    d = ImageDraw.Draw(im)
    c, r, w = n / 2, n * 13 / 64, round(n * 5 / 64)
    d.ellipse([c - r, c - r, c + r, c + r], outline=ACCENT, width=w)
    d.line([(c, n * 8 / 64), (c, n * 56 / 64)], fill=ACCENT, width=w)
    d.line([(n * 8 / 64, c), (n * 56 / 64, c)], fill=ACCENT, width=w)
    im.convert('RGB').resize((180, 180), Image.LANCZOS).save(PUBLIC / 'apple-touch-icon.png', optimize=True)


def og():
    W, H = 1200, 630
    portrait = Image.open(PUBLIC / 'hero' / 'portrait.webp').convert('RGBA')
    xray = Image.open(PUBLIC / 'hero' / 'xray.webp').convert('RGBA').resize(portrait.size, Image.LANCZOS)
    scale = (H - 40) / portrait.height
    size = (round(portrait.width * scale), H - 40)
    portrait, xray = portrait.resize(size, Image.LANCZOS), xray.resize(size, Image.LANCZOS)
    left = (W - size[0]) // 2

    paper = Image.new('RGBA', (W, H), PAPER + (255,))
    paper.alpha_composite(portrait, (left, H - size[1]))
    blue = Image.new('RGBA', (W, H), BLUE + (255,))
    blue.alpha_composite(grid((W, H), 30, LINE, 70))
    blue.alpha_composite(xray, (left, H - size[1]))

    # A soft, wavering vertical edge through the middle of the face.
    ys = np.arange(H)
    edge = W / 2 + 10 + 26 * np.sin(ys / 70.0) + 12 * np.sin(ys / 23.0 + 1.3)
    mask = Image.fromarray((np.arange(W)[None, :] > edge[:, None]).astype('uint8') * 255)
    out = paper.copy()
    out.paste(blue, (0, 0), mask.filter(ImageFilter.GaussianBlur(0.6)))
    rim = ImageDraw.Draw(out)
    rim.line([(float(edge[y]), float(y)) for y in ys], fill=ACCENT + (255,), width=4)
    out.convert('RGB').save(PUBLIC / 'og-image.jpg', quality=86, optimize=True, progressive=True)


if __name__ == '__main__':
    icon()
    og()
    print('wrote public/apple-touch-icon.png and public/og-image.jpg')
