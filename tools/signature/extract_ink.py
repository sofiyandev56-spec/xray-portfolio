"""
Lifts the ink out of a photo or scan of a signature: white ink on transparency,
the format tools/signature/pen_path.py, vectorize.py and src/motion/signature.js
expect.

  python3 tools/signature/extract_ink.py tools/signature/sources/autograph.png public/hero/autograph.png

The photo is enlarged first (so the edges stay smooth when the signature is shown
large), the paper's own shading and texture are measured locally and subtracted,
and what is left is cropped to the ink with a little margin.
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

SCALE = 2  # enlarge before extracting
src, out = sys.argv[1], sys.argv[2]

gray = Image.open(src).convert('L')
gray = gray.resize((gray.width * SCALE, gray.height * SCALE), Image.LANCZOS)
g = np.asarray(gray).astype(float)

# The paper's brightness around each point: the brightest nearby, softened.
paper = np.asarray(gray.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(12))).astype(float)
ink = np.clip((paper - g - 28) / 110, 0, 1) ** 0.85

alpha = Image.fromarray((ink * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.5))
a = np.asarray(alpha)
ys, xs = np.nonzero(a > 40)
pad = 24
box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(a.shape[1], xs.max() + pad), min(a.shape[0], ys.max() + pad))
alpha = alpha.crop(box)

result = Image.new('RGBA', alpha.size, (255, 255, 255, 0))
result.putalpha(alpha)
result.save(out, optimize=True)
print(f'wrote {out} ({result.width} x {result.height})')
