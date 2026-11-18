"""
Writes the brush-pen autograph the way a person signs it: where each stroke
starts and ends, in what order, and how fast the pen moves along it.

  python3 tools/signature/pen_path.py             # writes src/data/autograph-strokes.json
  python3 tools/signature/pen_path.py --preview   # also tools/signature/preview.png

The ink alone can't tell any of that (a traced line has two ends and no
direction), so the route is a plan read off the ink by eye,
tools/signature/autograph-plan.json: each pen-down stroke as points along the
ink, in writing order. It follows what handwriting research and forensic
document examination say about how people sign:

  Direction  A brush pen leaves thick downstrokes and thin upstrokes, and a
             pen that lands or lifts while moving leaves a tapered end (a
             "flying" start or finish), so the ink shows which way it went.
             Ovals (o, a) run counter-clockwise, lower loops (f, y) clockwise.
  Order      Left to right, a word at a time; a fluent hand lifts the pen
             between words, not inside them. Dotting an i, the underline, the
             dots and the crown are "delayed strokes", made once the name is done.
  Retracing  A fast hand goes back over a stem rather than lift (up and down
             the f, the second h, the n's first stroke): the pen moves, but no
             new ink appears.

Between two plan points the route follows the ink's centre line (the cheapest
path over the thinned ink), so the plan needs a point only at each turn or join.

Timing follows two findings from motor-control research:
  - the two-thirds power law (Lacquaniti, Terzuolo and Viviani, 1983): pen
    speed goes with the cube root of the radius of curvature, so long sweeps
    are fast, tight turns slow, and the pen all but stops where it reverses;
  - rapid strokes have a bell-shaped, lognormal speed profile (Plamondon's
    kinematic theory): the pen speeds up after landing and is still moving
    as it lifts.
Between strokes the pen travels through the air, for longer the further it goes.
The model sets the rhythm; DURATION sets how long the whole signature takes.

Each stroke is saved with its start time, its duration and its progress
sampled once a frame; src/motion/signature.js plays them back as written.
"""
import argparse
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vectorize import simplify, thin  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'public' / 'hero' / 'autograph.png'
PLAN = ROOT / 'tools' / 'signature' / 'autograph-plan.json'
OUT = ROOT / 'src' / 'data' / 'autograph-strokes.json'

DURATION = 3.6  # seconds for the whole signature, pen lifts included: unhurried enough to read

# The model, in its own time (scaled to DURATION at the end):
PACE = 1500  # pen speed in px/s on a curve of radius 100 px; the power law scales it by (radius / 100) ** (1/3)
RADIUS = (3, 700)  # px: tighter than this is a reversal, flatter is straight
CUSP = 110  # degrees: a turn this sharp at a plan point is a reversal...
DWELL = 0.015  # ...where the pen rests this many seconds
LAND, LIFT = 45, 35  # px over which the pen speeds up after landing, eases before lifting
AIR = (0.05, 0.0002, 0.22)  # seconds between strokes: base, per px travelled, most
GO_BACK = 0.06  # seconds more before a delayed stroke
DOT = 0.07  # seconds: a dot is a tap
FPS = 60  # progress samples per second of writing
STEPS = [(dx, dy, math.hypot(dx, dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def load_ink(src):
    ink = np.asarray(Image.open(src).convert('RGBA').getchannel('A')) > 110
    depth = np.zeros(ink.shape, np.int16)  # erosion depth: how far inside the stroke
    cur, k = ink.copy(), 0
    while cur.any():
        k += 1
        depth[cur] = k
        p = np.pad(cur, 1)
        cur = cur & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    skel = thin(ink).astype(bool)
    # Cheapest along the centre line; off it, dearer the nearer the edge.
    cost = np.where(ink, 3.0 + np.clip(8 - depth, 0, 8), np.inf)
    cost[skel] = 1.0
    return ink, depth, skel, cost.tolist()


def snap(pt, depth, skel, reach=10):
    """
    Where a plan point sits on the ink: the nearest pixel of the centre line,
    or the middle of a blob (like the balls on the crown's points) if a much
    deeper one is close.
    """
    x, y = pt
    y0, x0 = max(0, y - reach), max(0, x - reach)
    win = depth[y0:y + reach + 1, x0:x + reach + 1]
    ys, xs = np.mgrid[y0:y0 + win.shape[0], x0:x0 + win.shape[1]]
    near = np.hypot(xs - x, ys - y) <= reach
    on_line = near & skel[y0:y0 + win.shape[0], x0:x0 + win.shape[1]]
    if not on_line.any():
        raise SystemExit(f'plan point {pt} is not on the ink')
    d = np.where(on_line, np.hypot(xs - x, ys - y), np.inf)
    i = np.unravel_index(int(np.argmin(d)), d.shape)
    j = np.unravel_index(int(np.argmax(np.where(near, win, 0))), win.shape)
    if win[j] >= win[i] + 7:
        i = j
    return int(xs[i]), int(ys[i])


def route(cost, a, b, margin=80):
    """Cheapest path from a to b through the ink (Dijkstra), hugging the centre line."""
    H, W = len(cost), len(cost[0])
    x0, x1 = max(0, min(a[0], b[0]) - margin), min(W, max(a[0], b[0]) + margin + 1)
    y0, y1 = max(0, min(a[1], b[1]) - margin), min(H, max(a[1], b[1]) + margin + 1)
    best, came, heap = {a: 0.0}, {}, [(0.0, a)]
    while heap:
        d, p = heapq.heappop(heap)
        if p == b:
            break
        if d > best[p]:
            continue
        here = cost[p[1]][p[0]]
        for dx, dy, step in STEPS:
            q = (p[0] + dx, p[1] + dy)
            if not (x0 <= q[0] < x1 and y0 <= q[1] < y1):
                continue
            c = cost[q[1]][q[0]]
            if c == math.inf:
                continue
            nd = d + step * (c + here) / 2
            if nd < best.get(q, math.inf):
                best[q], came[q] = nd, p
                heapq.heappush(heap, (nd, q))
    else:
        raise SystemExit(f'no way through the ink from {a} to {b}')
    path = [b]
    while path[-1] != a:
        path.append(came[path[-1]])
    return path[::-1]


def turn(path, i, k=10):
    """Degrees the path turns at index i, judged over k pixels each side."""
    a = np.subtract(path[i], path[max(0, i - k)])
    b = np.subtract(path[min(len(path) - 1, i + k)], path[i])
    na, nb = np.hypot(*a), np.hypot(*b)
    if not na or not nb:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b) / (na * nb)))))


def run_out(tip, back, depth, short=3):
    """
    Where the ink really ends past a tip. Thinning stops short of a stroke's
    end by about half its width; carry on in the same direction to the edge
    (less `short` px, which the pen's round end covers). If the ink doesn't end
    within reach (three times the stroke's half-width) the tip isn't an end at
    all: leave it. A tip that lands with pressure, like the k's arm, is a blob.
    """
    d = np.subtract(tip, back).astype(float)
    n = np.hypot(*d)
    if not n:
        return tip
    d /= n
    H, W = depth.shape
    for k in range(1, min(30, 3 * int(depth[round(tip[1]), round(tip[0])]) + 4)):
        x, y = int(round(tip[0] + d[0] * k)), int(round(tip[1] + d[1] * k))
        if not (0 <= x < W and 0 <= y < H) or not depth[y, x]:
            k = max(0, k - short)
            return (tip[0] + d[0] * k, tip[1] + d[1] * k)
    return tip


def trace(via, kind, depth, skel, cost):
    """The pen's path through the plan points, smoothed, and where it reverses."""
    if kind == 'd':  # a dot: a tap, as planned
        return [tuple(map(float, p)) for p in via], []
    pts = [snap(p, depth, skel) for p in via]
    path, marks = [pts[0]], [0]
    for a, b in zip(pts, pts[1:]):
        if a != b:
            path += route(cost, a, b)[1:]
        marks.append(len(path) - 1)
    # Reversals stay sharp: smooth each run between them on its own.
    cuts = [0] + [m for m in marks[1:-1] if turn(path, m) > CUSP] + [len(path) - 1]
    # Run the two ends and every reversal out to the end of the ink.
    path = [tuple(map(float, p)) for p in path]
    last = len(path) - 1
    tips = {0: run_out(path[0], path[min(6, last)], depth), last: run_out(path[-1], path[max(0, last - 6)], depth)}
    for c in cuts[1:-1]:
        tips[c] = run_out(path[c], path[max(0, c - 6)], depth)
    line, cusps = [], []
    for a, b in zip(cuts, cuts[1:]):
        piece = [tips[a]] + path[a + 1:b] + [tips[b]]
        if len(piece) > 2:
            piece = smooth(simplify(piece, 1.0), rounds=2)
        line += piece if not line else piece[1:]
        cusps.append(len(line) - 1)
    return line, cusps[:-1]


def smooth(points, rounds=2):
    """Chaikin corner cutting: rounds off the stair-steps of a traced line, keeping its ends."""
    pts = list(points)
    for _ in range(rounds):
        if len(pts) < 3:
            break
        out = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            out += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        out.append(pts[-1])
        pts = out
    return pts


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def timing(line, cusps, kind):
    """Seconds the stroke takes, and its progress (0-1) sampled once a frame."""
    P = np.array(line, float)
    seg = np.hypot(*np.diff(P, axis=0).T)
    along = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(along[-1])
    if kind == 'd' or L < 8:
        return DOT, [0.0, 1.0]
    cusp_at = sorted({float(along[i]) for i in cusps})
    keep = np.concatenate([[True], seg > 1e-6])
    s, P = along[keep], P[keep]

    n = max(3, int(L // 2) + 1)  # a sample every ~2 px
    u = np.linspace(0, L, n)
    Q = np.column_stack([np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])])
    idx = np.arange(n)
    a, b = np.maximum(idx - 3, 0), np.minimum(idx + 3, n - 1)
    tangent = Q[b] - Q[a]
    angle = np.arctan2(tangent[:, 1], tangent[:, 0])
    turned = np.abs((angle[b] - angle[a] + np.pi) % (2 * np.pi) - np.pi)
    radius = np.clip((u[b] - u[a]) / np.maximum(turned, 1e-6), *RADIUS)
    v = PACE * (radius / 100) ** (1 / 3)  # the two-thirds power law
    v = np.convolve(np.pad(v, 4, mode='edge'), np.ones(9) / 9, mode='valid')  # a hand can't jump speeds
    v *= (0.4 + 0.6 * smoothstep(u / LAND)) * (0.55 + 0.45 * smoothstep((L - u) / LIFT))
    if kind == 'f':
        v *= 0.35 + 0.65 * np.sin(np.pi * (u / L) ** 0.8)  # one ballistic sweep, peaking early

    t = np.concatenate([[0.0], np.cumsum(np.diff(u) / ((v[:-1] + v[1:]) / 2))])
    # The pen rests a moment at each reversal before going back.
    ts, us = list(t), list(u)
    for c in reversed(cusp_at):
        i = int(np.searchsorted(u, c))
        if 0 < i < n:
            ts = ts[:i] + [ts[i - 1] + DWELL] + [x + DWELL for x in ts[i:]]
            us = us[:i] + [us[i - 1]] + us[i:]
    T = ts[-1]
    frames = max(2, round(T * FPS))
    progress = np.interp(np.linspace(0, T, frames + 1), ts, us) / L
    return T, [round(float(x), 4) for x in progress]


def pen_widths(strokes, ink, edge=1.5):
    """
    How wide the reveal pen must be for each stroke: just wide enough to uncover
    the ink nearer to that stroke than to any other (plus `edge` px so the
    outermost ink shows fully, not half-masked), so it doesn't also uncover ink
    that merely runs close by. Thick spots, like the balls on the crown, get a
    wider pen than thin lines.
    """
    ys, xs = np.nonzero(ink)
    pix = np.column_stack([xs, ys]).astype(np.float32)
    dist = np.full((len(strokes), len(pix)), np.inf, np.float32)
    for i, st in enumerate(strokes):
        P = np.array(st['line'], np.float32)
        seg = np.hypot(*np.diff(P, axis=0).T)
        along = np.concatenate([[0], np.cumsum(seg)])
        u = np.linspace(0, along[-1], max(2, int(along[-1]) + 1))
        pts = np.column_stack([np.interp(u, along, P[:, 0]), np.interp(u, along, P[:, 1])]).astype(np.float32)
        lo, hi = pts.min(0) - 40, pts.max(0) + 40
        near = np.nonzero(((pix >= lo) & (pix <= hi)).all(1))[0]
        best = np.full(len(near), np.inf, np.float32)
        for chunk in np.array_split(pts, max(1, len(pts) // 48)):
            best = np.minimum(best, ((pix[near, None, :] - chunk[None]) ** 2).sum(-1).min(1))
        dist[i, near] = np.sqrt(best)
    owner, nearest = dist.argmin(0), dist.min(0)
    widths = []
    for i in range(len(strokes)):
        mine = np.sort(nearest[owner == i])
        reach = float(mine[max(0, len(mine) - 4)]) if len(mine) else 0.0  # ignore the odd stray pixel
        widths.append(int(math.ceil(2 * (reach + edge))))
    return widths, int((nearest > (np.array(widths)[owner] / 2)).sum())


def main():
    ap = argparse.ArgumentParser(description='Route and time the autograph from its stroke plan.')
    ap.add_argument('--preview', nargs='?', type=Path, const=ROOT / 'tools' / 'signature' / 'preview.png')
    args = ap.parse_args()

    ink, depth, skel, cost = load_ink(SRC)
    H, W = ink.shape
    plan = json.loads(PLAN.read_text())['strokes']
    strokes, clock, prev = [], 0.0, None
    print(f'{"stroke":<34} {"length":>7} {"start":>6} {"time":>6} {"avg px/s":>9}')
    for item in plan:
        line, cusps = trace(item['via'], item['k'], depth, skel, cost)
        dur, progress = timing(line, cusps, item['k'])
        if prev is not None:
            gap = math.dist(prev, line[0])
            clock += min(AIR[2], AIR[0] + AIR[1] * gap) + (GO_BACK if item.get('delayed') else 0)
        strokes.append({'kind': item['k'], 'line': line, 'start': clock, 'dur': dur, 'progress': progress})
        clock += dur
        prev = line[-1]

    # Keep the rhythm, fit the time.
    scale = DURATION / clock
    for st, item in zip(strokes, plan):
        st['start'] *= scale
        st['dur'] *= scale
        length = sum(math.dist(a, b) for a, b in zip(st['line'], st['line'][1:]))
        print(f'{item["name"][:34]:<34} {length:7.0f} {st["start"]:6.2f} {st["dur"]:6.2f} {length / st["dur"]:9.0f}')
    print(f'model time {clock:.2f}s, scaled by {scale:.2f}')
    clock = DURATION

    pens, missed = pen_widths(strokes, ink)
    pen = int(np.median(pens))
    out = {
        'width': W,
        'height': H,
        # the invisible pen that reveals the ink along each stroke (w overrides it)
        'penWidth': pen,
        'duration': round(clock, 3),
        # k: l = letters, d = dot, f = flourish; p: the path; w: pen width;
        # t: start (s); d: duration (s); e: progress along p, sampled evenly over d
        'strokes': [
            {
                'k': st['kind'],
                'p': [[round(x, 1), round(y, 1)] for x, y in st['line']],
                **({'w': w} if w != pen else {}),
                't': round(st['start'], 3),
                'd': round(st['dur'], 3),
                'e': st['progress'],
            }
            for st, w in zip(strokes, pens)
        ],
    }
    OUT.write_text(json.dumps(out, separators=(',', ':')))
    print(
        f'{len(strokes)} strokes, {clock:.2f}s, pens {pens} px ({missed} stray ink px left out), '
        f'wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} kB)'
    )

    if args.preview:
        S = 1.4
        im = Image.new('RGB', (round(W * S), round(H * S)), (14, 30, 70))
        im.paste((80, 95, 140), (0, 0), Image.open(SRC).convert('RGBA').resize(im.size))
        d = ImageDraw.Draw(im)
        for i, st in enumerate(strokes, 1):
            pts = [(x * S, y * S) for x, y in st['line']]
            for j, (a, b) in enumerate(zip(pts, pts[1:])):  # yellow at the start to orange at the end
                k = j / max(1, len(pts) - 2)
                d.line([a, b], fill=(255, int(220 - 120 * k), int(60 - 40 * k)), width=3)
            (ax, ay), (bx, by) = pts[max(0, len(pts) - 4)], pts[-1]
            ang = math.atan2(by - ay, bx - ax)
            d.polygon([(bx, by)] + [(bx - 14 * math.cos(ang + s), by - 14 * math.sin(ang + s)) for s in (-0.45, 0.45)],
                      fill=(255, 70, 70))
            sx, sy = pts[0]
            d.ellipse([sx - 6, sy - 6, sx + 6, sy + 6], fill=(60, 230, 120))
            d.text((sx + 7, sy - 22), str(i), fill=(255, 255, 255))
        im.save(args.preview)
        print('preview', args.preview.relative_to(ROOT))


if __name__ == '__main__':
    main()
