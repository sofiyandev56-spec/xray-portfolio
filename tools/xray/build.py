"""
Builds public/hero/xray.webp: the picture revealed under the cursor in the hero.

Everything is aligned to the 843 x 818 frame of public/hero/portrait.webp, and the
output is drawn at twice that size. HeroScene stretches both images over the same
box, so they must keep the same aspect ratio.

Sources (tools/xray/sources):
  skull.jpg, skull-mask.png    frontal skull illustration and its cut-out mask
  macbook-air-teardown.jpg     a MacBook Air with the bottom case removed
  m4-chip.jpg                  the chip shown where the heat spreader was
  photo-keypoints.json         face and pose landmarks found in the original photo
                               (reference only; the numbers used are below)

Run from the project root (needs Pillow and NumPy):

  python3 tools/xray/build.py

Pass --preview to also write tools/xray/xray-preview.png (the result on blueprint blue).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'tools' / 'xray' / 'sources'
PORTRAIT = ROOT / 'public' / 'hero' / 'portrait.webp'
OUT = ROOT / 'public' / 'hero' / 'xray.webp'

W, H = 843, 818  # portrait frame; all coordinates below are in these units
SS = 2  # output scale
OW, OH = W * SS, H * SS

# Palette, matching src/styles/tokens.css
PAPER = (232, 236, 241)
LINE = (159, 178, 214)
BLUE = (20, 51, 122)
INK = (10, 24, 56)

# Where things are in the portrait (measured from the photo and its landmarks)
EYE_MID = (435.5, 197.5)  # midpoint between the pupils
EYE_ROLL = 4.5  # degrees; the head tilts so its right side (image right) is higher
CHIN_BONE = 143.0  # distance from EYE_MID to where the jawbone should end
LID = (107, 488, 662, 818)  # MacBook lid: left, top, right, bottom (cut at the desk)


def s(v):
    """Portrait units to output pixels."""
    return v * SS


def ramp(values, stops):
    """Map 0..1 values through colour stops [(t, (r, g, b)), ...]."""
    ts = [t for t, _ in stops]
    out = np.empty(values.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(values, ts, [rgb[c] for _, rgb in stops])
    return out


def levels(gray, mask=None, lo=2, hi=99):
    sample = gray[mask] if mask is not None else gray
    a, b = np.percentile(sample, [lo, hi])
    return np.clip((gray - a) / max(b - a, 1e-6), 0, 1)


def rgba(rgb, alpha):
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 255)]).astype('uint8'), 'RGBA')


def blank():
    return Image.new('RGBA', (OW, OH), (0, 0, 0, 0))


# ------------------------------------------------------------------ silhouette

def silhouette():
    """A faint outline of everything in the photo, traced from its alpha channel."""
    alpha = Image.open(PORTRAIT).convert('RGBA').getchannel('A').resize((OW, OH), Image.BILINEAR)
    solid = alpha.point(lambda v: 255 if v > 127 else 0)
    edge = np.asarray(solid.filter(ImageFilter.MaxFilter(5))).astype(int) - np.asarray(
        solid.filter(ImageFilter.MinFilter(3))
    ).astype(int)
    edge = Image.fromarray(np.clip(edge, 0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8))
    layer = Image.new('RGBA', (OW, OH), LINE + (0,))
    layer.putalpha(edge.point(lambda v: int(v * 0.6)))
    return layer


# ------------------------------------------------------------------ skull

# Rows in skull.jpg (523 x 790): top of the cranium, centre of the eye sockets,
# bottom of the chin. Columns: midpoint between the sockets.
SKULL_TOP, SKULL_ORBIT, SKULL_CHIN, SKULL_MID_X = 19, 325, 755, 266.5
SKULL_SCALE = 0.40  # socket spacing (223 px) to pupil spacing (89 px)


def skull():
    im = Image.open(SRC / 'skull.jpg').convert('RGB')
    sw, sh = im.size
    mask = Image.open(SRC / 'skull-mask.png').convert('L').resize((sw, sh), Image.BILINEAR)
    m = np.asarray(mask) > 127

    # Cyanotype: bone becomes paper white, shadow becomes deep blue.
    gray = np.asarray(im.convert('L')).astype(float)
    tone = ramp(
        levels(gray, m, 2, 99.5),
        [(0, INK), (0.25, (28, 60, 140)), (0.55, (112, 142, 202)), (0.8, (214, 224, 238)), (1, (247, 249, 252))],
    )
    alpha = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.6))).astype(float)
    art = np.dstack([tone, alpha])

    # The illustration's lower face is longer than the photo's, so scale it to the
    # eye spacing above the sockets and compress it gently below them, ending the
    # jaw at CHIN_BONE. Rows are resampled through a piecewise-linear map.
    k = SKULL_SCALE * SS
    out_w = round(sw * k)
    art = np.asarray(Image.fromarray(art.astype('uint8'), 'RGBA').resize((out_w, sh), Image.LANCZOS)).astype(float)

    above = SKULL_ORBIT * k  # output rows above the sockets
    blend_end = 420  # source row where the compressed scale is fully in effect
    mid = above + (blend_end - SKULL_ORBIT) * k * 0.92
    chin = above + CHIN_BONE * SS
    lower = (chin - mid) / (SKULL_CHIN - blend_end)
    src_rows = [0, SKULL_ORBIT, blend_end, SKULL_CHIN, sh - 1]
    dst_rows = [0, above, mid, chin, chin + (sh - 1 - SKULL_CHIN) * lower]
    out_h = int(np.ceil(dst_rows[-1])) + 1
    y = np.interp(np.arange(out_h), dst_rows, src_rows)
    y0 = np.floor(y).astype(int).clip(0, sh - 1)
    y1 = (y0 + 1).clip(0, sh - 1)
    f = (y - y0)[:, None, None]
    warped = art[y0] * (1 - f) + art[y1] * f

    # Place the socket midpoint on the eye midpoint, then tilt to match the head.
    layer = blank()
    piece = Image.fromarray(warped.clip(0, 255).astype('uint8'), 'RGBA')
    cx, cy = s(EYE_MID[0]), s(EYE_MID[1])
    layer.paste(piece, (round(cx - SKULL_MID_X * k), round(cy - above)))
    return layer.rotate(EYE_ROLL, resample=Image.BICUBIC, center=(cx, cy))


# ------------------------------------------------------------------ the rest of the skeleton
#
# Drawn here, not traced: proportions follow a frontal anatomy reference, and the
# positions follow the photo (shoulders and elbow from the pose landmarks, the
# neck from the chin and collar). Everything below the lid's top edge is covered
# by the MacBook, so only the neck, shoulder girdle, top of the rib cage and the
# arms beside the laptop really show.

MID_X = 448  # the body's midline
SHOULDER = 194  # half the distance between the shoulder joints
JOINT_Y = 462  # height of the shoulder joints


def bezier(p0, p1, p2, p3, n=48):
    p0, p1, p2, p3 = (np.array(p, float) for p in (p0, p1, p2, p3))
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def line(a, b, n=32):
    t = np.linspace(0, 1, n)[:, None]
    return np.array(a, float) * (1 - t) + np.array(b, float) * t


def tube(d, pts, widths):
    """
    A bone as a filled outline around a centre line, with a width at each point
    (so shafts can taper and ends can flare), and round ends.
    """
    pts = np.asarray(pts, float)
    widths = np.interp(np.linspace(0, 1, len(pts)), np.linspace(0, 1, len(widths)), widths)
    tangent = np.gradient(pts, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True) + 1e-9
    normal = np.stack([-tangent[:, 1], tangent[:, 0]], axis=1)
    left = pts + normal * widths[:, None] / 2
    right = pts - normal * widths[:, None] / 2
    outline = [tuple(s(v) for v in p) for p in np.vstack([left, right[::-1]])]
    d.polygon(outline, fill=255)
    for p, w in ((pts[0], widths[0]), (pts[-1], widths[-1])):
        d.ellipse([s(p[0] - w / 2), s(p[1] - w / 2), s(p[0] + w / 2), s(p[1] + w / 2)], fill=255)


def blob(d, cx, cy, rx, ry=None, angle=0):
    ry = rx if ry is None else ry
    t = np.linspace(0, 2 * np.pi, 48)
    c, si = np.cos(np.radians(angle)), np.sin(np.radians(angle))
    xs, ys = rx * np.cos(t), ry * np.sin(t)
    d.polygon([(s(cx + x * c - y * si), s(cy + x * si + y * c)) for x, y in zip(xs, ys)], fill=255)


def xray(draw_fn, opacity=1.0, cortex=2.2):
    """
    Render bones the way a radiograph shows them: the dense outer wall (cortex)
    bright, the hollow middle dimmer, everything a little grainy.
    """
    m = Image.new('L', (OW, OH), 0)
    draw_fn(ImageDraw.Draw(m))
    m = m.filter(ImageFilter.GaussianBlur(0.6))
    mask = np.asarray(m).astype(float) / 255
    inner = np.asarray(m.filter(ImageFilter.MinFilter(int(round(s(cortex))) * 2 + 1))).astype(float) / 255
    inner = np.asarray(Image.fromarray((inner * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(s(1.2)))).astype(float) / 255
    rim = np.clip(mask - inner, 0, 1)
    body = np.asarray(m.filter(ImageFilter.GaussianBlur(s(3)))).astype(float) / 255

    value = 0.38 * mask + 0.62 * rim + 0.12 * body
    rng = np.random.default_rng(11)
    grain = Image.fromarray((rng.random((OH // 5, OW // 5)) * 255).astype('uint8')).resize((OW, OH), Image.BICUBIC)
    value *= 0.88 + 0.12 * np.asarray(grain).astype(float) / 255
    tone = ramp(np.clip(value, 0, 1), [(0, (36, 68, 150)), (0.35, (92, 122, 190)), (0.6, (168, 186, 222)), (0.85, (228, 234, 244)), (1, (250, 251, 253))])
    return rgba(tone, mask * 255 * opacity)


def skeleton():
    def side(sign, x):
        return MID_X + sign * x

    def scapulae(d):
        # Seen through the ribs: the coracoid hook under each collarbone, the
        # acromion over the joint, and the top of the blade behind.
        for sg in (-1, 1):
            tube(d, bezier((side(sg, 72), 474), (side(sg, 110), 462), (side(sg, 150), 458), (side(sg, 180), 458)), [5, 5, 6])
            tube(d, bezier((side(sg, 172), 474), (side(sg, 160), 468), (side(sg, 146), 463), (side(sg, 136), 466)), [9, 7, 5])
            tube(d, line((side(sg, 176), 446), (side(sg, 204), 450)), [9, 10])

    def ribs(d):
        # Upper ribs: out from the spine, round the side, down to the breastbone.
        for k in range(4):
            y = 449 + 14 * k
            reach = 62 + 40 * k
            for sg in (-1, 1):
                back = bezier((side(sg, 14), y), (side(sg, reach * 0.75), y - 15 - 2 * k), (side(sg, reach * 1.08), y + 4), (side(sg, reach * 0.98), y + 34 + 6 * k))
                tube(d, back, [5, 6, 6.5, 6])
                front = bezier(back[-1], (side(sg, reach * 0.8), y + 46 + 7 * k), (side(sg, 40), y + 40 + 9 * k), (side(sg, 19), y + 30 + 9 * k))
                tube(d, front, [5.5, 4.5, 3.5])  # costal cartilage, thinner

    def sternum(d):
        top = 462
        outline = [(430, top), (437, top + 5), (448, top + 7), (459, top + 5), (466, top), (464, top + 14),
                   (461, top + 26), (458, top + 44), (438, top + 44), (435, top + 26), (432, top + 14)]
        d.polygon([(s(x), s(y)) for x, y in outline], fill=255)

    def collarbones(d):
        for sg in (-1, 1):
            c = bezier((side(sg, 19), 466), (side(sg, 70), 474), (side(sg, 120), 446), (side(sg, 186), 448))
            tube(d, c, [12, 9, 7, 7.5, 9, 12])

    def spine(d):
        # C3 to T1: vertebral bodies with disc gaps, and side (transverse) processes.
        for i in range(6):
            t = i / 5
            cx, cy = 442 + 6 * t, 352 + 95 * t
            w = 25 + 10 * t
            reach = w / 2 + (9 if i < 5 else 15)
            d.rounded_rectangle([s(cx - w / 2), s(cy - 6.5), s(cx + w / 2), s(cy + 6.5)], radius=s(4), fill=255)
            for sg in (-1, 1):
                blob(d, cx + sg * (reach - 4), cy - 1, 6.5, 3.6, angle=sg * -8)

    def arm(d, sg, elbow, hand_ulna=None, hand_radius=None):
        head = (side(sg, SHOULDER), JOINT_Y)
        ex, ey = elbow
        # humerus: ball head, a bump for the greater tubercle, a shaft that narrows
        # then flares into the epicondyles at the elbow
        blob(d, head[0], head[1], 17, 16)
        blob(d, head[0] + sg * 13, head[1] - 3, 8, 9)
        shaft = line((head[0] + sg * -2, head[1] + 10), (ex, ey - 4))
        tube(d, shaft, [16, 11, 10, 9.5, 10, 13, 22])
        ux, uy = ex - head[0], ey - head[1]
        n = np.hypot(ux, uy)
        px, py = -uy / n, ux / n
        tube(d, line((ex - px * 16, ey - py * 16), (ex + px * 16, ey + py * 16)), [9, 11, 9])
        if hand_ulna:
            tube(d, line((ex + 4, ey + 6), hand_ulna), [11, 8, 6.5, 6])  # ulna: thick at the elbow
            tube(d, line((ex - 6, ey + 4), hand_radius), [6, 6.5, 8, 10])  # radius: thick at the wrist

    def arms(d):
        arm(d, -1, (197, 656))
        arm(d, 1, (803, 652), hand_ulna=(706, 738), hand_radius=(696, 724))

    layers = [
        xray(scapulae, opacity=0.6),
        xray(ribs, opacity=0.85, cortex=1.6),
        xray(sternum),
        xray(spine),
        xray(collarbones),
        xray(arms),
    ]
    out = blank()
    union = blank()
    for layer in layers:
        union.alpha_composite(layer)
    out.alpha_composite(glow(union, s(6), 0.16))
    for layer in layers:
        out.alpha_composite(layer)
    return out


def glow(layer, radius, strength):
    a = layer.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    g = Image.new('RGBA', (OW, OH), PAPER + (0,))
    g.putalpha(a.point(lambda v: int(v * strength)))
    return g


# ------------------------------------------------------------------ headphones and cans

def dashed_circle(d, cx, cy, r, fill, width, dash=14):
    for a in range(0, 360, dash * 2):
        d.arc([cx - r, cy - r, cx + r, cy + r], a, a + dash, fill=fill, width=width)


def props():
    layer = blank()
    d = ImageDraw.Draw(layer)
    # headphone drivers, seen through the ear cups
    for cx, cy, r in ((321, 226, 27), (554, 212, 25)):
        d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], outline=LINE + (255,), width=round(s(1.6)))
        dashed_circle(d, s(cx), s(cy), s(r * 0.62), LINE + (230,), round(s(1.1)))
        rr = r * 0.26
        d.ellipse(
            [s(cx - rr), s(cy - rr), s(cx + rr), s(cy + rr)], fill=BLUE + (255,), outline=PAPER + (255,), width=round(s(1.6))
        )

    # drink cans: the rim, the liquid level, and a few bubbles
    for x0, x1, top, level in ((14, 108, 590, 640), (662, 772, 563, 618)):
        cx, rx = (x0 + x1) / 2, (x1 - x0) / 2 - 3
        d.ellipse([s(cx - rx), s(top + 1), s(cx + rx), s(top + 13)], outline=LINE + (255,), width=round(s(1.4)))
        xs = np.linspace(x0 + 5, x1 - 5, 64)
        ys = level + 2.6 * np.sin((xs - x0) / (x1 - x0) * np.pi * 4)
        d.line([(s(x), s(y)) for x, y in zip(xs, ys)], fill=PAPER + (255,), width=round(s(1.8)), joint='curve')
        for fx, dy, r in ((0.3, 34, 3.2), (0.62, 62, 2.2), (0.42, 96, 4), (0.72, 128, 2.6), (0.25, 150, 2)):
            bx, by = x0 + (x1 - x0) * fx, level + dy
            d.ellipse([s(bx - r), s(by - r), s(bx + r), s(by + r)], outline=LINE + (255,), width=round(s(1.2)))
    return layer


# ------------------------------------------------------------------ MacBook

# In macbook-air-teardown.jpg (2000 x 1500): the outline of the body, and the heat
# spreader over the system chip, which the M4 image replaces.
BODY = (52, 92, 1957, 1418)
SPREADER = (900, 213, 1250, 448)
CHIP_SIZE = 84  # portrait units; a little larger than the spreader so the logo reads


def macbook():
    x0, y0, x1, y1 = LID
    k = (x1 - x0) / (BODY[2] - BODY[0])  # fit the body's width to the lid

    td = Image.open(SRC / 'macbook-air-teardown.jpg').convert('RGB').crop(BODY)
    gray = np.asarray(td.convert('L')).astype(float)
    tone = ramp(
        levels(gray, None, 1, 99.5),
        [(0, (8, 20, 52)), (0.22, (22, 50, 116)), (0.55, (104, 134, 196)), (0.85, (214, 224, 238)), (1, (247, 249, 252))],
    )
    body = rgba(tone, np.full(gray.shape, 255.0))
    bw, bh = round(s(x1 - x0)), round((BODY[3] - BODY[1]) * k * SS)
    body = body.resize((bw, bh), Image.LANCZOS)

    # The chip, in full colour, where the heat spreader was.
    chip = Image.open(SRC / 'm4-chip.jpg').convert('RGB').crop((25, 20, 316, 312))
    side = round(s(CHIP_SIZE))
    chip = chip.resize((side, side), Image.LANCZOS).convert('RGBA')
    cmask = Image.new('L', (side, side), 0)
    ImageDraw.Draw(cmask).rounded_rectangle([0, 0, side - 1, side - 1], radius=round(s(5)), fill=255)
    chip.putalpha(cmask)
    ccx = ((SPREADER[0] + SPREADER[2]) / 2 - BODY[0]) * k * SS
    ccy = ((SPREADER[1] + SPREADER[3]) / 2 - BODY[1]) * k * SS
    frame = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    pad = s(3)
    ImageDraw.Draw(frame).rounded_rectangle(
        [ccx - side / 2 - pad, ccy - side / 2 - pad, ccx + side / 2 + pad, ccy + side / 2 + pad],
        radius=s(7),
        fill=PAPER + (255,),
    )
    body.alpha_composite(frame)
    body.alpha_composite(chip, (round(ccx - side / 2), round(ccy - side / 2)))

    # Only the part inside the lid shows; its top corners are rounded like the lid.
    lid = Image.new('L', (OW, OH), 0)
    ImageDraw.Draw(lid).rounded_rectangle([s(x0), s(y0), s(x1), s(y1 + 40)], radius=s(14), fill=255)
    layer = blank()
    layer.paste(body, (round(s(x0)), round(s(y0))))
    layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer.getchannel('A')), np.asarray(lid))))
    ImageDraw.Draw(layer).rounded_rectangle(
        [s(x0) + 1, s(y0) + 1, s(x1) - 1, s(y1 + 40)], radius=s(14), outline=PAPER + (255,), width=round(s(1.6))
    )
    return layer


# ------------------------------------------------------------------ compose

def build():
    out = blank()
    for layer in (silhouette(), skeleton()):
        out.alpha_composite(layer)
    sk = skull()
    out.alpha_composite(glow(sk, s(8), 0.22))
    out.alpha_composite(sk)
    out.alpha_composite(props())
    out.alpha_composite(macbook())

    # Fully transparent pixels take the background blue, so texture filtering at
    # the edges blends toward the background instead of toward black.
    a = np.asarray(out).copy()
    clear = a[..., 3] == 0
    a[clear, :3] = BLUE
    out = Image.fromarray(a, 'RGBA')
    out.save(OUT, 'WEBP', quality=88, alpha_quality=100, method=6)
    print(f'wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} kB, {OW} x {OH})')

    if '--preview' in sys.argv:
        bg = Image.new('RGBA', (OW, OH), BLUE + (255,))
        bg.alpha_composite(out)
        path = ROOT / 'tools' / 'xray' / 'xray-preview.png'
        bg.convert('RGB').save(path)
        print(f'wrote {path.relative_to(ROOT)}')


if __name__ == '__main__':
    build()
