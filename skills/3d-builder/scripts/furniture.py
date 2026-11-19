"""Furniture symbols for draw_plans.py (Python 3 standard library only).

Each piece is drawn in a local frame W wide (u, along its back) and D deep (v), with the
back at v = D and the front at v = 0. `facing` rotates the piece so its front faces
N, E, S or W. In the layout, `x, y` is the south-west corner of the placed footprint and
`w`, `d` its east-west and north-south size, whatever the facing.
"""
import math
from xml.sax.saxutils import escape

INK = "#6b6359"        # furniture outline
FILL = "#f6f2ea"       # furniture body
SOFT = "#ffffff"       # cushions, pillows, duvet
WET = "#eef4f8"        # sanitary ware
WET_INK = "#4f6f86"
TOP = "#ece6db"        # worktops
RUG = "#efe7d8"
GREEN, GREEN_FILL = "#5f8a4c", "#e3eedb"
CAR, CAR_FILL = "#7a7f86", "#eceef0"


class Pen:
    """Collects SVG elements in local (u, v) mm; v up. The group transform does the rest."""

    def __init__(self, sw):
        self.sw = sw
        self.out = []

    def _a(self, fill, stroke, sw, dash, extra=""):
        s = f' fill="{fill}" stroke="{stroke}" stroke-width="{(sw or self.sw):.1f}"'
        if dash:
            s += f' stroke-dasharray="{dash}"'
        return s + extra

    def rect(self, u, v, w, h, fill=FILL, stroke=INK, r=0, sw=None, dash=None):
        if w <= 0 or h <= 0:
            return
        rr = f' rx="{r:.1f}"' if r else ""
        self.out.append(f'<rect x="{u:.1f}" y="{v:.1f}" width="{w:.1f}" height="{h:.1f}"{rr}'
                        f'{self._a(fill, stroke, sw, dash)}/>')

    def circle(self, u, v, r, fill=FILL, stroke=INK, sw=None, dash=None):
        self.out.append(f'<circle cx="{u:.1f}" cy="{v:.1f}" r="{r:.1f}"{self._a(fill, stroke, sw, dash)}/>')

    def ellipse(self, u, v, rx, ry, fill=FILL, stroke=INK, sw=None):
        self.out.append(f'<ellipse cx="{u:.1f}" cy="{v:.1f}" rx="{rx:.1f}" ry="{ry:.1f}"'
                        f'{self._a(fill, stroke, sw, None)}/>')

    def line(self, u1, v1, u2, v2, stroke=INK, sw=None, dash=None):
        self.out.append(f'<line x1="{u1:.1f}" y1="{v1:.1f}" x2="{u2:.1f}" y2="{v2:.1f}"'
                        f'{self._a("none", stroke, sw, dash)}/>')

    def poly(self, pts, fill=FILL, stroke=INK, sw=None, dash=None):
        p = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
        self.out.append(f'<polygon points="{p}"{self._a(fill, stroke, sw, dash)}/>')

    def path(self, d, fill="none", stroke=INK, sw=None):
        self.out.append(f'<path d="{d}"{self._a(fill, stroke, sw, None)}/>')


# ---- symbols: f(pen, W, D, item) --------------------------------------------------

def bed(p, W, D, it):
    p.rect(0, 0, W, D, r=40)
    p.rect(0, D - 90, W, 90, fill=TOP)                                # headboard
    n = 1 if W < 1300 else 2
    gap = 90
    pw = (W - gap * (n + 1)) / n
    for i in range(n):
        p.rect(gap + i * (pw + gap), D - 90 - 60 - 380, pw, 380, fill=SOFT, r=70)
    top = D * 0.66
    p.rect(30, 30, W - 60, top - 30, fill=SOFT, r=30)                 # duvet
    p.line(30, top - 220, W - 30, top - 220)                          # fold
    p.poly([(W - 30, 30), (W - 30, 380), (W - 380, 30)], fill=TOP)    # turned-down corner


def nightstand(p, W, D, it):
    p.rect(0, 0, W, D, r=20)
    p.circle(W / 2, D / 2, min(W, D) * 0.27, fill=SOFT)


def _cushions(p, u0, u1, v0, v1, n):
    cw = (u1 - u0) / n
    for i in range(n):
        p.rect(u0 + i * cw + 15, v0 + 15, cw - 30, v1 - v0 - 30, fill=SOFT, r=60)


def sofa(p, W, D, it):
    back, arm = min(220, D * 0.25), it.get("arm", 160)
    p.rect(0, 0, W, D, r=80)
    p.rect(0, D - back, W, back, fill=TOP, r=60)
    p.rect(0, 0, arm, D - back + 40, fill=TOP, r=60)
    p.rect(W - arm, 0, arm, D - back + 40, fill=TOP, r=60)
    n = it.get("seats") or max(1, min(4, round((W - 2 * arm) / 700)))
    _cushions(p, arm, W - arm, 0, D - back, n)


def sofa_l(p, W, D, it):
    """L-sofa: full-width seat along the back plus a return of depth `seat` down one side.
    `return_side` "left"/"right" as seen by someone seated, facing the front."""
    s = it.get("seat", 950)
    back = 220
    left = it.get("return_side", "left") == "left"     # sitter faces -v; their left is +u
    a = W - s if left else 0                           # return occupies u in [a, a + s]
    outline = ([(0, D - s), (a, D - s), (a, 0), (W, 0), (W, D), (0, D)] if left else
               [(0, 0), (s, 0), (s, D - s), (W, D - s), (W, D), (0, D)])
    p.poly(outline)
    p.rect(0, D - back, W, back, fill=TOP, r=60)                       # back along the long side
    if left:
        p.rect(W - back, 0, back, D, fill=TOP, r=60)                   # back along the return
        p.rect(0, D - s, 160, s - back + 40, fill=TOP, r=60)           # arm at the open end
        p.rect(a, 0, s - back, 160, fill=TOP, r=60)
        n = max(1, round((a - 160) / 750))
        _cushions(p, 160, W - back, D - s, D - back, n + 1)
        _cushions(p, a, W - back, 160, D - s, max(1, round((D - s - 160) / 750)))
    else:
        p.rect(0, 0, back, D, fill=TOP, r=60)
        p.rect(W - 160, D - s, 160, s - back + 40, fill=TOP, r=60)
        p.rect(back, 0, s - back, 160, fill=TOP, r=60)
        n = max(1, round((W - s - 160) / 750))
        _cushions(p, back, W - 160, D - s, D - back, n + 1)
        _cushions(p, back, s, 160, D - s, max(1, round((D - s - 160) / 750)))


def armchair(p, W, D, it):
    sofa(p, W, D, {**it, "seats": 1, "arm": min(150, W * 0.18)})


def chair(p, W, D, it):
    p.rect(0, 0, W, D * 0.85, r=60)
    p.rect(W * 0.08, D * 0.78, W * 0.84, D * 0.22, fill=TOP, r=40)


def stool(p, W, D, it):
    p.circle(W / 2, D / 2, min(W, D) / 2 - 10)
    p.circle(W / 2, D / 2, min(W, D) / 2 - 80, fill=SOFT)


def _chair_at(p, cu, cv, ang, size=460):
    """A dining chair centred at (cu, cv), its back pointing along angle `ang` (radians)."""
    c, s = math.cos(ang), math.sin(ang)
    h = size / 2

    def tr(x, y):  # local chair coords: back toward +y
        return (cu + x * s + y * c, cv - x * c + y * s)
    p.poly([tr(-h, -h), tr(h, -h), tr(h, h * 0.55), tr(-h, h * 0.55)])
    p.poly([tr(-h * 0.85, h * 0.55), tr(h * 0.85, h * 0.55), tr(h * 0.85, h), tr(-h * 0.85, h)], fill=TOP)


def table(p, W, D, it):
    seats, ends = it.get("seats", 0), it.get("ends", False)
    if seats:
        side = (seats - (2 if ends else 0)) // 2
        for i in range(side):
            u = W * (i + 0.5) / side
            _chair_at(p, u, -200, -math.pi / 2)
            _chair_at(p, u, D + 200, math.pi / 2)
        if ends:
            _chair_at(p, -200, D / 2, math.pi)
            _chair_at(p, W + 200, D / 2, 0)
    p.rect(0, 0, W, D, r=30)
    p.rect(60, 60, W - 120, D - 120, fill="none", sw=p.sw * 0.6)


def round_table(p, W, D, it):
    r = min(W, D) / 2
    n = it.get("seats", 0)
    for i in range(n):
        a = math.pi / 2 + 2 * math.pi * i / n + it.get("seat_offset", 0) * math.pi / 180
        _chair_at(p, W / 2 + (r + 200) * math.cos(a), D / 2 + (r + 200) * math.sin(a), a)
    p.circle(W / 2, D / 2, r)
    p.circle(W / 2, D / 2, r - 60, fill="none", sw=p.sw * 0.6)


def coffee_table(p, W, D, it):
    p.rect(0, 0, W, D, r=40)
    p.rect(80, 80, W - 160, D - 160, fill=SOFT, r=20)


def side_table(p, W, D, it):
    p.circle(W / 2, D / 2, min(W, D) / 2 - 10)


def desk(p, W, D, it):
    if it.get("chair", True):
        cw = 560
        cu, cv = W / 2, -330
        p.circle(cu, cv, cw / 2 - 20)
        p.path(f"M {cu - cw / 2 + 40:.1f} {cv + 120:.1f} Q {cu:.1f} {cv + cw / 2 + 60:.1f} "
               f"{cu + cw / 2 - 40:.1f} {cv + 120:.1f}", sw=p.sw * 2.2)
    p.rect(0, 0, W, D)
    mw = min(W * 0.55, it.get("screen", 1050))
    p.rect(W / 2 - mw / 2, D - 160, mw, 50, fill="#555555", stroke="#555555")  # screen
    if it.get("speakers"):
        for u in (W / 2 - mw / 2 - 260, W / 2 + mw / 2 + 80):
            p.rect(u, D - 280, 180, 220, fill=TOP)


def tv(p, W, D, it):
    p.rect(0, 0, W, D)
    for i in range(1, 3):
        p.line(W * i / 3, 0, W * i / 3, D, sw=p.sw * 0.6)
    sw = min(W * 0.85, it.get("screen", 1600))
    p.rect(W / 2 - sw / 2, D - 70, sw, 40, fill="#444444", stroke="#444444")


def cabinet(p, W, D, it):
    p.rect(0, 0, W, D)
    n = max(1, round(W / 500))
    for i in range(1, n):
        p.line(W * i / n, 0, W * i / n, D, sw=p.sw * 0.6)
    p.line(0, 40, W, 40, sw=p.sw * 0.6)


def wardrobe(p, W, D, it):
    p.rect(0, 0, W, D)
    p.line(0, D / 2, W, D / 2, dash=f"{p.sw * 6:.0f} {p.sw * 3:.0f}")      # rail
    step = 160
    u = step / 2
    while u < W:
        p.line(u - 90, D / 2 - 170, u + 90, D / 2 + 170, sw=p.sw * 0.6)   # hangers
        u += step


def shelf(p, W, D, it):
    p.rect(0, 0, W, D)
    p.line(0, 0, W, D, sw=p.sw * 0.6)


def tall(p, W, D, it):
    p.rect(0, 0, W, D)
    n = max(1, round(W / 600))
    for i in range(n):
        u0, u1 = W * i / n, W * (i + 1) / n
        p.line(u0, 0, u1, D, sw=p.sw * 0.6)
        p.line(u0, D, u1, 0, sw=p.sw * 0.6)
        if i:
            p.line(u0, 0, u0, D)


def counter(p, W, D, it):
    p.rect(0, 0, W, D, fill=TOP)
    p.line(0, 50, W, 50, sw=p.sw * 0.6)


def sink(p, W, D, it):
    n = it.get("bowls", 1)
    bw = (W - 80 * (n + 1)) / n
    for i in range(n):
        p.rect(80 + i * (bw + 80), 80, bw, D - 220, fill=WET, stroke=WET_INK, r=50)
        p.circle(80 + i * (bw + 80) + bw / 2, 80 + (D - 220) / 2, 25, fill=WET_INK, stroke=WET_INK)
    p.circle(W / 2, D - 70, 30, fill=SOFT, stroke=WET_INK)


def hob(p, W, D, it):
    n = it.get("burners", 4)
    p.rect(30, 30, W - 60, D - 60, fill="#f4f4f4", r=20)
    if n == 2:
        r = min(W / 4, D / 2) - 60
        for u in (W / 4, 3 * W / 4):
            p.circle(u, D / 2, r, fill="none")
            p.circle(u, D / 2, r * 0.45, fill="none")
    else:
        r = min(W, D) / 4 - 40
        for u in (W / 4, 3 * W / 4):
            for v in (D / 4 + 20, 3 * D / 4 - 20):
                p.circle(u, v, r, fill="none")


def appliance(p, W, D, it):
    p.rect(20, 20, W - 40, D - 40, fill=SOFT)
    if it.get("drum"):
        p.circle(W / 2, D / 2, min(W, D) * 0.33, fill="none")


def wc(p, W, D, it):
    tw = min(W * 0.9, 420)
    p.rect(W / 2 - tw / 2, D - 180, tw, 180, fill=WET, stroke=WET_INK, r=20)     # cistern / frame
    p.ellipse(W / 2, D - 180 - 260, 190, 270, fill=WET, stroke=WET_INK)
    p.ellipse(W / 2, D - 180 - 270, 120, 190, fill=SOFT, stroke=WET_INK)


def basin(p, W, D, it):
    p.rect(0, 0, W, D, fill=TOP if it.get("counter", True) else WET, stroke=WET_INK)
    if it.get("trough"):                                   # one long trough bowl, single tap
        tw = W - 2 * min(200, W * 0.12)
        p.rect(W / 2 - tw / 2, D * 0.17, tw, D * 0.56, fill=WET, stroke=WET_INK, r=D * 0.2)
        p.circle(W / 2, D - 60, 22, fill=WET_INK, stroke=WET_INK)
        return
    n = it.get("basins", 1)
    for i in range(n):
        cu = W * (i + 0.5) / n
        p.ellipse(cu, D * 0.45, min(W / n * 0.32, 220), D * 0.28, fill=WET, stroke=WET_INK)
        p.circle(cu, D - 60, 22, fill=WET_INK, stroke=WET_INK)


def shower(p, W, D, it):
    p.rect(0, 0, W, D, fill=WET, stroke=WET_INK)
    p.line(0, 0, W, D, stroke=WET_INK, sw=p.sw * 0.5)
    p.line(0, D, W, 0, stroke=WET_INK, sw=p.sw * 0.5)
    p.circle(W / 2, D / 2, 50, fill=SOFT, stroke=WET_INK)


def tub(p, W, D, it):
    p.rect(0, 0, W, D, fill=WET, stroke=WET_INK, r=40)
    p.rect(90, 90, W - 180, D - 180, fill=SOFT, stroke=WET_INK, r=min(W, D) * 0.3)
    p.circle(W * 0.18, D / 2, 35, fill=WET, stroke=WET_INK)


def glass(p, W, D, it):
    p.rect(0, 0, W, D, fill="#d9ecf7", stroke="#2b6cb0", sw=p.sw * 0.8)


def drain(p, W, D, it):
    p.rect(0, 0, W, D, fill="#ffffff", stroke=WET_INK)
    n = max(2, int(W / 60))
    for i in range(1, n):
        p.line(W * i / n, 0, W * i / n, D, stroke=WET_INK, sw=p.sw * 0.4)


def piano(p, W, D, it):
    """Stage piano on a stand; the player sits at the front."""
    p.rect(0, 0, W, D, r=20)
    kd = D * 0.45
    p.rect(60, 30, W - 120, kd, fill=SOFT)
    n = 26
    for i in range(1, n):
        u = 60 + (W - 120) * i / n
        p.line(u, 30 + kd * 0.35, u, 30 + kd, sw=p.sw * 0.5)


def bench(p, W, D, it):
    p.rect(0, 0, W, D, r=30)
    n = max(2, round(D / 120))
    for i in range(1, n):
        p.line(30, D * i / n, W - 30, D * i / n, sw=p.sw * 0.5)


def drums(p, W, D, it):
    p.rect(0, 0, W, D, fill="#f1ede6", dash=f"{p.sw * 5:.0f} {p.sw * 3:.0f}")    # riser
    cu = W / 2
    p.circle(cu, D * 0.58, 260, fill=SOFT)                    # kick
    p.circle(cu - 330, D * 0.42, 170, fill=SOFT)              # snare
    p.circle(cu - 200, D * 0.80, 140, fill=SOFT)              # tom 1
    p.circle(cu + 200, D * 0.80, 140, fill=SOFT)              # tom 2
    p.circle(cu + 380, D * 0.45, 190, fill=SOFT)              # floor tom
    for u, v, r in ((cu - 600, D * 0.75, 200), (cu + 560, D * 0.88, 230), (cu - 620, D * 0.30, 160)):
        p.circle(u, v, r, fill="none", dash=f"{p.sw * 3:.0f} {p.sw * 2:.0f}")   # cymbals
    p.circle(cu, D * 0.18, 170)                               # throne


def amp(p, W, D, it):
    p.rect(0, 0, W, D, fill="#e4ddd2", r=20)
    p.line(40, 60, W - 40, 60, sw=p.sw * 0.6)


def guitar(p, W, D, it):
    """Guitar on a stand, seen from above: body at the front, neck to the back."""
    cu = W / 2
    p.rect(cu - 35, D * 0.5, 70, D * 0.45, fill=TOP)
    p.ellipse(cu, D * 0.18, W * 0.42, D * 0.16)
    p.ellipse(cu, D * 0.38, W * 0.32, D * 0.12)
    p.circle(cu, D * 0.30, W * 0.1, fill=SOFT)


def rug(p, W, D, it):
    p.rect(0, 0, W, D, fill=RUG, stroke="#c9bba3", sw=p.sw * 0.6)
    p.rect(120, 120, W - 240, D - 240, fill="none", stroke="#c9bba3", sw=p.sw * 0.6,
           dash=f"{p.sw * 4:.0f} {p.sw * 3:.0f}")


def plant(p, W, D, it):
    r = min(W, D) / 2
    cu, cv = W / 2, D / 2
    p.circle(cu, cv, r - 10, fill=GREEN_FILL, stroke=GREEN)
    n = 7
    for i in range(n):
        a = 2 * math.pi * i / n
        p.line(cu + r * 0.25 * math.cos(a), cv + r * 0.25 * math.sin(a),
               cu + r * 0.9 * math.cos(a), cv + r * 0.9 * math.sin(a), stroke=GREEN, sw=p.sw * 0.7)
    p.circle(cu, cv, r * 0.25, fill="#ffffff", stroke=GREEN)


def tree(p, W, D, it):
    r = min(W, D) / 2
    cu, cv = W / 2, D / 2
    n = 9
    pts = []
    for i in range(2 * n):
        a = math.pi * i / n
        rr = r if i % 2 == 0 else r * 0.86
        pts.append((cu + rr * math.cos(a), cv + rr * math.sin(a)))
    p.poly(pts, fill=GREEN_FILL, stroke=GREEN)
    p.circle(cu, cv, r * 0.5, fill="none", stroke=GREEN, sw=p.sw * 0.5)
    p.circle(cu, cv, r * 0.08, fill=GREEN, stroke=GREEN)


def palm(p, W, D, it):
    r = min(W, D) / 2
    cu, cv = W / 2, D / 2
    for i in range(9):
        a = 2 * math.pi * i / 9 + 0.2
        ex, ey = cu + r * math.cos(a), cv + r * math.sin(a)
        mx, my = cu + r * 0.55 * math.cos(a + 0.25), cv + r * 0.55 * math.sin(a + 0.25)
        p.path(f"M {cu:.1f} {cv:.1f} Q {mx:.1f} {my:.1f} {ex:.1f} {ey:.1f}", stroke=GREEN, sw=p.sw * 1.6)
    p.circle(cu, cv, r * 0.1, fill=GREEN, stroke=GREEN)


def car(p, W, D, it):
    """Car seen from above, front at v = 0."""
    p.rect(0, 0, W, D, fill=CAR_FILL, stroke=CAR, r=W * 0.22)
    p.poly([(W * 0.12, D * 0.30), (W * 0.88, D * 0.30), (W * 0.82, D * 0.40), (W * 0.18, D * 0.40)],
           fill="#cfd5db", stroke=CAR)                                   # windscreen
    p.rect(W * 0.16, D * 0.40, W * 0.68, D * 0.36, fill="none", stroke=CAR, r=W * 0.08)  # roof
    p.poly([(W * 0.18, D * 0.76), (W * 0.82, D * 0.76), (W * 0.86, D * 0.84), (W * 0.14, D * 0.84)],
           fill="#cfd5db", stroke=CAR)                                   # rear window
    for u in (-60, W - 20):
        p.rect(u, D * 0.30, 80, 120, fill=CAR_FILL, stroke=CAR, r=20)    # mirrors


def lounger(p, W, D, it):
    """Sun lounger: head (raised back) at v = D."""
    p.rect(0, 0, W, D, r=60)
    p.rect(40, D * 0.62, W - 80, D * 0.38 - 40, fill=SOFT, r=50)
    p.rect(40, 40, W - 80, D * 0.62 - 60, fill=SOFT, r=40)


def daybed(p, W, D, it):
    p.rect(0, 0, W, D, r=60)
    p.rect(60, 60, W - 120, D - 120, fill=SOFT, r=50)
    n = max(1, round(W / 600))
    cw = (W - 120) / n
    for i in range(n):
        p.rect(60 + i * cw + 20, D - 60 - 260, cw - 40, 220, fill=TOP, r=60)


def panel(p, W, D, it):
    p.rect(0, 0, W, D, fill="#e9e9e9", stroke="#666666")


SYMBOLS = {
    "bed": bed, "nightstand": nightstand, "sofa": sofa, "sofa_l": sofa_l, "armchair": armchair,
    "chair": chair, "stool": stool, "table": table, "round_table": round_table,
    "coffee_table": coffee_table, "side_table": side_table, "desk": desk, "tv": tv,
    "cabinet": cabinet, "sideboard": cabinet, "wardrobe": wardrobe, "shelf": shelf, "tall": tall,
    "counter": counter, "sink": sink, "hob": hob, "appliance": appliance, "wc": wc, "basin": basin,
    "shower": shower, "tub": tub, "glass": glass, "drain": drain, "piano": piano, "bench": bench,
    "drums": drums, "amp": amp, "guitar": guitar, "rug": rug, "plant": plant, "tree": tree,
    "palm": palm, "car": car, "lounger": lounger, "daybed": daybed, "panel": panel,
}


def local_size(it):
    w, d = float(it["w"]), float(it["d"])
    return (w, d) if it.get("facing", "S").upper() in ("N", "S") else (d, w)


def transform(it):
    """SVG matrix from local (u, v) to SVG user space (y down)."""
    x, y, w, d = (float(it[k]) for k in ("x", "y", "w", "d"))
    W, D = local_size(it)
    f = it.get("facing", "S").upper()
    if f == "S":
        m = (1, 0, 0, -1, x, -y)
    elif f == "N":
        m = (-1, 0, 0, 1, x + W, -(y + D))
    elif f == "E":
        m = (0, -1, -1, 0, x + w, -y)
    elif f == "W":
        m = (0, 1, 1, 0, x, -(y + d))
    else:
        raise ValueError(f"furniture facing must be N, E, S or W, not {f!r}")
    return "matrix(" + " ".join(f"{v:.1f}" if isinstance(v, float) else str(v) for v in m) + ")"


def draw_item(it, k, thin):
    kind = it.get("type")
    if kind not in SYMBOLS:
        raise ValueError(f"unknown furniture type {kind!r} (known: {', '.join(sorted(SYMBOLS))})")
    W, D = local_size(it)
    pen = Pen(thin * k)
    SYMBOLS[kind](pen, W, D, it)
    out = [f'<g transform="{transform(it)}">'] + pen.out + ['</g>']
    if it.get("label"):
        cx, cy = float(it["x"]) + float(it["w"]) / 2, float(it["y"]) + float(it["d"]) / 2
        size = 1.5 * k
        out.append(f'<text x="{cx:.1f}" y="{-cy + size * 0.35:.1f}" font-size="{size:.1f}" '
                   f'text-anchor="middle" fill="{INK}">{escape(str(it["label"]))}</text>')
    return out
