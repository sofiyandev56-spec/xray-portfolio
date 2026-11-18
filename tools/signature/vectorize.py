"""
Traces the centre lines of the pen strokes in an ink image (white on
transparency) and writes them, in writing order, to a JSON file. Used for the
footer signature and for the name the intro writes.

The site never draws these lines itself. They are the path a thick, invisible
"pen" follows to reveal the real ink, so the signature appears stroke by stroke
(see src/motion/signature.js).

Run from the project root (needs Pillow and NumPy):

  # the signature (the defaults)
  python3 tools/signature/vectorize.py --preview

  # the name in the intro (rendered by tools/signature/render_name.py)
  python3 tools/signature/vectorize.py --src public/hero/name.png \
      --out src/data/name-strokes.json --mode name --scale 1 --preview

--mode signature  letters left to right, then dots, then the long flourishes
--mode name       letters strictly left to right, then the i-dots
--scale           trace at this fraction of full size (1 keeps fine hairlines)
--preview [path]  also write an image with the strokes numbered in order

The writing order is worked out by classify() below.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'public' / 'hero' / 'signature.png'
OUT = ROOT / 'src' / 'data' / 'signature-strokes.json'
SCALE = 0.5  # trace at half size; coordinates are scaled back up (see --scale)
MIN_LENGTH = 6  # traced pixels; shorter fragments are noise from thinning


def thin(img):
    """Zhang-Suen thinning: reduce strokes to one-pixel centre lines."""
    img = img.copy().astype(np.uint8)
    while True:
        changed = False
        for step in (0, 1):
            p = np.pad(img, 1)
            n = [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]
            b = sum(x.astype(int) for x in n)
            a = sum(((n[i] == 0) & (n[(i + 1) % 8] == 1)).astype(int) for i in range(8))
            if step == 0:
                c = (n[0] * n[2] * n[4] == 0) & (n[2] * n[4] * n[6] == 0)
            else:
                c = (n[0] * n[2] * n[6] == 0) & (n[0] * n[4] * n[6] == 0)
            kill = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            if kill.any():
                img[kill] = 0
                changed = True
        if not changed:
            return img


OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def neighbours(sk, y, x):
    h, w = sk.shape
    return [(y + dy, x + dx) for dy, dx in OFFSETS if 0 <= y + dy < h and 0 <= x + dx < w and sk[y + dy, x + dx]]


def trace(sk):
    """Split the skeleton at junctions and walk each piece into a polyline."""
    sk = sk.astype(bool).copy()
    degree = {}
    for y, x in zip(*np.nonzero(sk)):
        degree[(y, x)] = len(neighbours(sk, y, x))
    junctions = {p for p, d in degree.items() if d >= 3}
    body = sk.copy()
    for y, x in junctions:
        body[y, x] = False

    seen = np.zeros_like(body)
    strokes = []
    pts = list(zip(*np.nonzero(body)))
    # Start from endpoints first so open strokes are walked end to end.
    pts.sort(key=lambda p: len(neighbours(body, *p)))
    for start in pts:
        if seen[start]:
            continue
        line = [start]
        seen[start] = True
        cur = start
        while True:
            nxt = [q for q in neighbours(body, *cur) if not seen[q]]
            if not nxt:
                break
            # prefer 4-connected steps, which keep the walk on the centre line
            nxt.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            cur = nxt[0]
            seen[cur] = True
            line.append(cur)
        # Reattach the junction pixels at either end, so pieces meet.
        for end in (0, -1):
            y, x = line[end]
            js = [q for q in junctions if abs(q[0] - y) <= 1 and abs(q[1] - x) <= 1]
            if js:
                if end == 0:
                    line.insert(0, js[0])
                else:
                    line.append(js[0])
        if len(line) >= MIN_LENGTH:
            strokes.append(line)
    return strokes


def simplify(points, eps):
    """Ramer-Douglas-Peucker."""
    if len(points) < 3:
        return points
    a, b = np.array(points[0], float), np.array(points[-1], float)
    ab = b - a
    norm = np.hypot(*ab) or 1.0
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / norm for p in points[1:-1]]
    i = int(np.argmax(d)) + 1
    if d[i - 1] > eps:
        return simplify(points[: i + 1], eps)[:-1] + simplify(points[i:], eps)
    return [points[0], points[-1]]


def tangent(line, at_end, k=6):
    """Unit direction of travel arriving at one end of a traced line."""
    pts = line[-k:] if at_end else line[:k][::-1]
    (y0, x0), (y1, x1) = pts[0], pts[-1]
    v = np.array([x1 - x0, y1 - y0], float)
    n = np.hypot(*v)
    return v / n if n else v


def join(fragments, radius=7):
    """
    Rebuild whole pen strokes from fragments split at crossings. Fragment ends
    that meet are paired by good continuation: the pair whose directions line up
    best (straightest path through the crossing) is joined first.
    """
    ends = []  # (fragment index, at_end, point, arriving tangent)
    for i, line in enumerate(fragments):
        for at_end in (False, True):
            y, x = line[-1] if at_end else line[0]
            ends.append((i, at_end, np.array([x, y], float), tangent(line, at_end)))

    pairs = []
    for a in range(len(ends)):
        for b in range(a + 1, len(ends)):
            ia, ea, pa, ta = ends[a]
            ib, eb, pb, tb = ends[b]
            if ia == ib or np.hypot(*(pa - pb)) > radius:
                continue
            straight = float(np.dot(ta, tb))  # -1 when one carries straight on into the other
            if straight < -0.35:
                pairs.append((straight, a, b))
    pairs.sort()
    link = {}
    for _, a, b in pairs:
        if a not in link and b not in link:
            link[a] = b
            link[b] = a

    def end_id(i, at_end):
        return i * 2 + (1 if at_end else 0)

    used = set()
    strokes = []

    def walk(i, forward):
        chain = []
        while i not in used:
            used.add(i)
            line = fragments[i] if forward else fragments[i][::-1]
            chain.extend(line if not chain else line[1:])
            out = end_id(i, forward)  # the end we leave from
            nxt = link.get(out)
            if nxt is None:
                break
            j, j_at_end = nxt // 2, nxt % 2 == 1
            i, forward = j, not j_at_end  # enter j at the paired end
        return chain

    # Open strokes first: start from ends nobody continues into.
    for i in range(len(fragments)):
        for at_end in (False, True):
            if i not in used and end_id(i, at_end) not in link:
                strokes.append(walk(i, not at_end))
    for i in range(len(fragments)):  # what is left is closed loops
        if i not in used:
            strokes.append(walk(i, True))
    return strokes


def build(mode='signature'):
    im = Image.open(SRC).convert('RGBA')
    W, H = im.size
    alpha = im.getchannel('A').resize((round(W * SCALE), round(H * SCALE)), Image.LANCZOS)
    ink = (np.asarray(alpha) > 110).astype(np.uint8)
    full_ink = np.asarray(im.getchannel('A')) > 110

    sk = thin(ink)
    lines = join(trace(sk))

    strokes = []
    for line in lines:
        pts = [(x / SCALE, y / SCALE) for y, x in line]  # (x, y) at full size
        pts = simplify(pts, 1.6)
        length = sum(np.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        if length >= 12:
            strokes.append({'points': pts, 'length': length})

    total = sum(s['length'] for s in strokes) or 1
    width = float(full_ink.sum()) / total

    # The thickest stroke: erode the ink one pixel at a time until (almost) none
    # is left. The reveal pen must be at least this wide to uncover heavy shades.
    m, start, rounds = Image.fromarray((full_ink * 255).astype('uint8')), full_ink.sum(), 0
    while rounds < 60 and np.asarray(m).astype(bool).sum() > start * 0.004:
        m = m.filter(ImageFilter.MinFilter(3))
        rounds += 1
    thickest = rounds * 2

    # Dots and other marks too small to thin: any ink blob no stroke passes near.
    covered = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(covered)
    for st in strokes:
        d.line(st['points'], fill=255, width=int(width * 2.4))
    rest = full_ink & (np.asarray(covered) == 0)
    seen = np.zeros_like(rest)
    for y, x in zip(*np.nonzero(rest)):
        if seen[y, x]:
            continue
        stack, blob = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            blob.append((cy, cx))
            for dy, dx in OFFSETS:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < H and 0 <= nx < W and rest[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(blob) > 60:
            ys, xs = zip(*blob)
            cx, cy = float(np.mean(xs)), float(np.mean(ys))
            seg = long_axis(np.column_stack([xs, ys]).astype(float))
            if mode == 'name' and seg is not None:
                # A sliver of a thick stroke, not a dot: write it as a short stroke.
                strokes.append({'points': seg, 'length': float(np.hypot(*np.subtract(seg[1], seg[0])))})
            else:
                strokes.append({'points': [(cx - 2, cy), (cx + 2, cy)], 'length': 4, 'dot': True})
    return W, H, strokes, width, thickest


def pen_tour(strokes, reach=20):
    """
    Order strokes the way a pen would travel: from the end of each stroke, carry
    on into whichever stroke starts (or ends) right there, preferring the one that
    continues straightest. When nothing connects, lift the pen and move to the
    next stroke in reading order. Strokes are flipped as needed so each one is
    drawn from the end the pen arrives at.
    """
    def direction(pts, at_end):
        a, b = (pts[-2], pts[-1]) if at_end else (pts[1], pts[0])
        v = np.array(b, float) - np.array(a, float)
        n = np.hypot(*v)
        return v / n if n else v

    remaining = list(strokes)
    order = []

    def take(st, reverse):
        remaining.remove(st)
        if reverse:
            st['points'] = st['points'][::-1]
        order.append(st)

    while remaining:
        if order:
            last = order[-1]['points']
            pen, heading = np.array(last[-1], float), direction(last, True)
            best, best_cost = None, None
            for st in remaining:
                for reverse in (False, True):
                    pts = st['points'][::-1] if reverse else st['points']
                    gap = np.hypot(*(np.array(pts[0], float) - pen))
                    if gap > reach:
                        continue
                    onward = -direction(pts, False)  # direction of travel leaving the start
                    cost = gap + 18 * (1 - float(np.dot(heading, onward))) / 2
                    if best_cost is None or cost < best_cost:
                        best, best_cost = (st, reverse), cost
            if best:
                take(*best)
                continue
        # Pen lift: the next unwritten stroke in reading order (by its centre, so
        # a long descender reaching left doesn't jump the queue), from its left end.
        st = min(remaining, key=lambda st: sum(p[0] for p in st['points']) / len(st['points']))
        take(st, st['points'][0][0] > st['points'][-1][0])
    return order


def long_axis(pts, ratio=2.2, minimum=20):
    """The end points of a blob's long axis, or None when the blob is roughly round."""
    centre = pts.mean(0)
    _, sv, vt = np.linalg.svd(pts - centre, full_matrices=False)
    proj = (pts - centre) @ vt[0]
    across = (pts - centre) @ vt[1]
    major, minor = proj.max() - proj.min(), (across.max() - across.min()) or 1
    if major < minimum or major / minor < ratio:
        return None
    a, b = centre + vt[0] * proj.min(), centre + vt[0] * proj.max()
    return [tuple(a), tuple(b)]


def patch_gaps(ordered, ink, pen):
    """
    Thick strokes that cross others can lose bits of centre line, leaving ink the
    pen never passes over. Return a short stroke along each such gap's long axis;
    added before the pen tour, they bridge the breaks so the pen runs straight on.
    """
    H, W = ink.shape
    cover = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(cover)
    for st in ordered:
        pts = st['points']
        d.line(pts, fill=255, width=int(pen), joint='curve')
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - pen / 2, y - pen / 2, x + pen / 2, y + pen / 2], fill=255)
    miss = ink & (np.asarray(cover) == 0)
    seen = np.zeros_like(miss)
    patches = []
    for y, x in zip(*np.nonzero(miss)):
        if seen[y, x]:
            continue
        stack, blob = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            blob.append((cx, cy))
            for dy, dx in OFFSETS:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < H and 0 <= nx < W and miss[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(blob) < 12:
            continue
        pts = np.array(blob, float)
        centre = pts.mean(0)
        axis = np.linalg.svd(pts - centre, full_matrices=False)[2][0]
        proj = (pts - centre) @ axis
        a, b = centre + axis * proj.min(), centre + axis * proj.max()
        patches.append((centre, [tuple(a), tuple(b)]))

    return [
        {'points': seg, 'length': float(np.hypot(seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]))}
        for _, seg in patches
    ]


def classify(strokes, ink_width, mode='signature'):
    """
    Writing order, the way a signature is usually made:
      letters  left to right, each drawn left-to-right or top-to-bottom
      dots     after the letters
      flourish the long sweeps (oval, underlines) last, upper ones first
    Tiny pieces left at crossings are tagged so the animation can draw them
    alongside their neighbours instead of pausing for them.
    """
    def span(st):
        xs = [p[0] for p in st['points']]
        ys = [p[1] for p in st['points']]
        return max(xs) - min(xs), max(ys) - min(ys), min(xs), sum(ys) / len(ys)

    body = [st for st in strokes if not st.get('dot')]
    for st in strokes:
        dx, dy, minx, meany = span(st)
        st['minx'], st['meany'] = minx, meany
        if st.get('dot'):
            near = min(
                (np.hypot(st['points'][0][0] - p[0], st['points'][0][1] - p[1]) for b in body for p in b['points']),
                default=1e9,
            )
            st['kind'] = 'd' if near > ink_width * 2.5 else 't'
        elif mode == 'signature' and dx > 450:
            st['kind'] = 'f'
        elif st['length'] < 24:
            st['kind'] = 't'
        else:
            st['kind'] = 'l'
        # Direction of travel: left to right for wide strokes, top to bottom for tall ones.
        (x0, y0), (x1, y1) = st['points'][0], st['points'][-1]
        if (dx >= dy and x0 > x1) or (dx < dy and y0 > y1):
            st['points'] = st['points'][::-1]

    if mode == 'name':
        letters = pen_tour([st for st in strokes if st['kind'] in 'lt'])
    else:
        letters = sorted((st for st in strokes if st['kind'] in 'lt'), key=lambda st: st['minx'])
    dots = sorted((st for st in strokes if st['kind'] == 'd'), key=lambda st: st['minx'])
    flourishes = sorted((st for st in strokes if st['kind'] == 'f'), key=lambda st: st['meany'])
    return letters + dots + flourishes


def main():
    global SRC, OUT, SCALE
    ap = argparse.ArgumentParser(description='Trace pen strokes from an ink image.')
    ap.add_argument('--src', type=Path, default=SRC)
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--mode', choices=['signature', 'name'], default='signature')
    ap.add_argument('--scale', type=float, default=SCALE)
    ap.add_argument('--preview', nargs='?', type=Path, const=ROOT / 'tools' / 'signature' / 'preview.png')
    args = ap.parse_args()
    SRC, OUT, SCALE = args.src.resolve(), args.out.resolve(), args.scale

    W, H, strokes, width, thickest = build(args.mode)
    pen = max(width * 2.6, thickest * 1.25 + 4)
    if args.mode == 'name':
        ink = np.asarray(Image.open(SRC).convert('RGBA').getchannel('A')) > 110
        patches = patch_gaps(strokes, ink, pen)
        strokes += patches
        print(f'patched {len(patches)} gaps')
    ordered = classify(strokes, width, args.mode)
    out = {
        'width': W,
        'height': H,
        'inkWidth': round(width, 1),
        # how wide the invisible reveal pen should be to cover every stroke
        'penWidth': round(pen, 1),
        # k: l = letter, t = tiny piece at a crossing, d = dot, f = flourish
        'strokes': [{'k': st['kind'], 'p': [[round(x, 1), round(y, 1)] for x, y in st['points']]} for st in ordered],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    kinds = {k: sum(1 for st in ordered if st['kind'] == k) for k in 'ltdf'}
    print(
        f'{len(ordered)} strokes {kinds}, ink ~{width:.1f}px, thickest ~{thickest}px, '
        f'pen {out["penWidth"]}px, wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} kB)'
    )

    if args.preview:
        im = Image.new('RGB', (W, H), (20, 51, 122))
        im.paste((90, 110, 160), (0, 0), Image.open(SRC).convert('RGBA'))
        d = ImageDraw.Draw(im)
        colours = {'l': (255, 200, 60), 't': (255, 120, 120), 'd': (120, 255, 160), 'f': (140, 220, 255)}
        for i, st in enumerate(ordered):
            pts = st['points']
            d.line(pts, fill=colours[st['kind']], width=3)
            d.ellipse([pts[0][0] - 5, pts[0][1] - 5, pts[0][0] + 5, pts[0][1] + 5], fill=(255, 255, 255))
            if st['kind'] != 't':
                mx, my = pts[len(pts) // 2]
                d.text((mx + 6, my - 14), str(i), fill=(255, 255, 255))
        im.save(args.preview)
        print('preview', args.preview)


if __name__ == '__main__':
    main()
