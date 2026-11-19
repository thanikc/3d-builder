#!/usr/bin/env python3
"""Draw floor plans as SVG files from a layout JSON (Python 3 standard library only).

Usage:
    python3 draw_plans.py models/<name>/plans/layout.json [--out DIR]

Checks the layout for errors, writes one SVG per floor to <out>/floor-<id>.svg
(default <out>: the folder of the JSON file) and prints the room areas per floor.
An optional structural grid (axes 1, 2, 3 / A, B, C with columns) is drawn on every floor.
All floors share the same frame, so the sheets line up when overlaid.
Layout format: see references/floorplans.md.
"""
import argparse
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# Sizes on paper in mm. Multiplied by the drawing scale to get model mm.
PAPER = {"text": 2.5, "small": 1.8, "title": 3.5, "line": 0.25, "thin": 0.13,
         "margin": 12.0, "dim_gap": 7.0, "title_block": 16.0, "bubble": 3.0}
EPS = 1.0  # mm: wall endpoints closer than this count as joined
COLORS = {"exterior": "#222222", "interior": "#555555", "window": "#2b6cb0",
          "dim": "#444444", "fixture": "#888888", "text": "#111111", "muted": "#666666",
          "grid": "#c05621", "column": "#111111"}


class LayoutError(Exception):
    pass


def add(a, b): return (a[0] + b[0], a[1] + b[1])
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def mul(a, k): return (a[0] * k, a[1] * k)
def norm(a): return math.hypot(a[0], a[1])
def close(a, b): return norm(sub(a, b)) < EPS


def pt(p):
    """Model point (y up) -> SVG coordinate string (y down)."""
    return f"{p[0]:.1f},{-p[1]:.1f}"


def poly(points, **attrs):
    return f'<polygon points="{" ".join(pt(p) for p in points)}"{fmt_attrs(attrs)}/>'


def line(a, b, **attrs):
    return (f'<line x1="{a[0]:.1f}" y1="{-a[1]:.1f}" x2="{b[0]:.1f}" y2="{-b[1]:.1f}"'
            f'{fmt_attrs(attrs)}/>')


def text(p, s, size, **attrs):
    attrs.setdefault("text_anchor", "middle")
    return (f'<text x="{p[0]:.1f}" y="{-p[1]:.1f}" font-size="{size:.1f}"{fmt_attrs(attrs)}>'
            f'{escape(str(s))}</text>')


def fmt_attrs(attrs):
    return "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())


def metres(mm):
    return f"{mm / 1000:.2f} m"


class Wall:
    def __init__(self, d):
        try:
            self.id = str(d["id"])
            self.a, self.b = tuple(d["from"]), tuple(d["to"])
        except KeyError as e:
            raise LayoutError(f"wall {d} is missing {e}")
        self.t = float(d.get("thickness", 200))
        self.type = d.get("type", "interior")
        self.L = norm(sub(self.b, self.a))
        if self.L < EPS:
            raise LayoutError(f"wall {self.id} has zero length")
        self.u = mul(sub(self.b, self.a), 1 / self.L)
        self.n = (-self.u[1], self.u[0])  # points to the left of from -> to
        self.ext_a = self.ext_b = 0.0     # extension past the endpoints at corners
        self.openings = []

    def at(self, s, side=0.0):
        """Point s mm along the centreline from 'from', shifted sideways by 'side'."""
        return add(add(self.a, mul(self.u, s)), mul(self.n, side))

    def quad(self, s0, s1):
        h = self.t / 2
        return [self.at(s0, -h), self.at(s1, -h), self.at(s1, h), self.at(s0, h)]

    def pieces(self):
        """Solid stretches of the wall between openings, as (s0, s1)."""
        out, s = [], -self.ext_a
        for o in self.openings:
            if o["offset"] > s + 0.01:
                out.append((s, o["offset"]))
            s = o["offset"] + o["width"]
        if self.L + self.ext_b > s + 0.01:
            out.append((s, self.L + self.ext_b))
        return out


def build_walls(floor):
    walls = {}
    for d in floor.get("walls", []):
        w = Wall(d)
        if w.id in walls:
            raise LayoutError(f"duplicate wall id {w.id}")
        walls[w.id] = w
    # Where wall endpoints meet (corners), extend each wall by half the other wall's
    # thickness so the corner is filled and the outer faces meet cleanly.
    for w in walls.values():
        for end in ("a", "b"):
            p = getattr(w, end)
            ext = max((o.t / 2 for o in walls.values()
                       if o is not w and (close(p, o.a) or close(p, o.b))), default=0.0)
            setattr(w, "ext_" + end, ext)
    for d in floor.get("openings", []):
        wid = str(d.get("wall"))
        if wid not in walls:
            raise LayoutError(f"opening {d} refers to unknown wall {wid!r}")
        w = walls[wid]
        o = dict(d, offset=float(d["offset"]), width=float(d["width"]),
                 type=d.get("type", "door"))
        if o["offset"] < 0 or o["offset"] + o["width"] > w.L + 0.01:
            raise LayoutError(f"opening on wall {wid} (offset {o['offset']:.0f}, width "
                              f"{o['width']:.0f}) does not fit the wall length {w.L:.0f}")
        w.openings.append(o)
    for w in walls.values():
        w.openings.sort(key=lambda o: o["offset"])
        for o1, o2 in zip(w.openings, w.openings[1:]):
            if o1["offset"] + o1["width"] > o2["offset"] + 0.01:
                raise LayoutError(f"openings overlap on wall {w.id} at offset {o2['offset']:.0f}")
    return walls


def grid_labels(n, letters):
    """Default grid labels: 1, 2, 3 ... or A, B, ... Z, AA, AB ..."""
    if not letters:
        return [str(i + 1) for i in range(n)]
    out = []
    for i in range(n):
        s, i = "", i + 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        out.append(s)
    return out


def parse_grid(d):
    """Validate the layout's "grid" and return it normalised, or None if there is none.

    x lines run north-south (numbered 1, 2, 3 ...), y lines run east-west (lettered A, B, C ...).
    """
    if not d:
        return None
    g = {}
    for axis, letters in (("x", False), ("y", True)):
        pos = [float(v) for v in d.get(axis, [])]
        if any(b <= a for a, b in zip(pos, pos[1:])):
            raise LayoutError(f"grid {axis} positions must be in increasing order")
        labels = [str(v) for v in d.get(axis + "_labels", grid_labels(len(pos), letters))]
        if len(labels) != len(pos):
            raise LayoutError(f"grid has {len(pos)} {axis} lines but {len(labels)} {axis}_labels")
        g[axis] = list(zip(labels, pos))
    if not g["x"] and not g["y"]:
        raise LayoutError("grid has no x or y lines")
    names = [n for n, _ in g["x"] + g["y"]]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise LayoutError(f"duplicate grid labels {', '.join(dupes)}")
    col = d.get("column", {})
    if "diameter" in col:
        g["column"] = {"shape": "round", "w": float(col["diameter"]), "d": float(col["diameter"])}
    else:
        g["column"] = {"shape": "square", "w": float(col.get("w", 300)), "d": float(col.get("d", col.get("w", 300)))}
    g["columns"] = grid_columns(g, d.get("columns", []), "grid")
    return g


def grid_columns(g, spec, where):
    """Column centres from "all" or a list of [x label, y label] pairs."""
    xs, ys = dict(g["x"]), dict(g["y"])
    if spec == "all":
        return [(xl, yl, (x, y)) for yl, y in g["y"] for xl, x in g["x"]]
    out = []
    for c in spec:
        if not isinstance(c, (list, tuple)) or len(c) != 2:
            raise LayoutError(f'{where} column {c!r} must be "all" or [x label, y label] like ["1", "A"]')
        xl, yl = str(c[0]), str(c[1])
        if xl not in xs or yl not in ys:
            raise LayoutError(f"{where} column {[xl, yl]} refers to an unknown grid line")
        out.append((xl, yl, (xs[xl], ys[yl])))
    return out


def floor_columns(grid, floor):
    """The columns on this floor: the floor's own "columns" if given, else the grid's."""
    if not grid:
        if "columns" in floor:
            raise LayoutError(f"floor {floor.get('id')} has columns but the layout has no grid")
        return []
    if "columns" in floor:
        return grid_columns(grid, floor["columns"], f"floor {floor.get('id')}")
    return grid["columns"]


def column_rect(grid, c):
    w, d = grid["column"]["w"], grid["column"]["d"]
    return {"x": c[0] - w / 2, "y": c[1] - d / 2, "w": w, "d": d}


def grid_points(grid):
    """Corners spanned by the grid lines and columns, so the frame includes them."""
    xs = [x for _, x in grid["x"]]
    ys = [y for _, y in grid["y"]]
    pts = [(x, y) for x in xs for y in ys] or [(x, 0.0) for x in xs] or [(0.0, y) for y in ys]
    for _, _, c in grid["columns"]:
        pts += rect_points(column_rect(grid, c))
    return pts


def draw_grid(grid, frame, k):
    """Dash-dot grid lines with labelled bubbles and spacing dimensions above and right of the frame."""
    fx0, fy0, fx1, fy1 = frame
    g, r = PAPER["dim_gap"] * k, PAPER["bubble"] * k
    sw = f"{PAPER['thin'] * k:.1f}"
    dash = f"{4 * k:.1f} {k:.1f} {0.6 * k:.1f} {k:.1f}"
    out = ['<g id="grid">']
    for axis in ("x", "y"):
        lines_ = grid[axis]
        for label, v in lines_:
            if axis == "x":
                a, b, c = (v, fy0), (v, fy1 + 2 * g), (v, fy1 + 2 * g + r)
            else:
                a, b, c = (fx0, v), (fx1 + 2 * g, v), (fx1 + 2 * g + r, v)
            out.append(line(a, b, stroke=COLORS["grid"], stroke_width=sw, stroke_dasharray=dash))
            out.append(f'<circle cx="{c[0]:.1f}" cy="{-c[1]:.1f}" r="{r:.1f}" fill="#ffffff" '
                       f'stroke="{COLORS["grid"]}" stroke-width="{PAPER["line"] * k:.1f}"/>')
            size = PAPER["text"] * k * (1 if len(label) < 3 else 0.7)
            out.append(text((c[0], c[1] - size * 0.35), label, size, fill=COLORS["grid"], font_weight="bold"))
        for (_, v0), (_, v1) in zip(lines_, lines_[1:]):
            if axis == "x":
                out += draw_dimension((v0, fy1), (v1, fy1), (0, g), metres(v1 - v0), k)
            else:
                out += draw_dimension((fx1, v0), (fx1, v1), (g, 0), metres(v1 - v0), k)
    out.append('</g>')
    return out


def draw_column(grid, c, k):
    """A column as a white square or circle with a cross, visible on top of walls."""
    w, d = grid["column"]["w"], grid["column"]["d"]
    x, y = c
    sw = f"{PAPER['line'] * k:.1f}"
    thin = f"{PAPER['thin'] * k:.1f}"
    if grid["column"]["shape"] == "round":
        r = w / 2
        q = r * math.sqrt(0.5)
        return [f'<circle cx="{x:.1f}" cy="{-y:.1f}" r="{r:.1f}" fill="#ffffff" stroke="{COLORS["column"]}" '
                f'stroke-width="{sw}"/>',
                line((x - q, y - q), (x + q, y + q), stroke=COLORS["column"], stroke_width=thin),
                line((x - q, y + q), (x + q, y - q), stroke=COLORS["column"], stroke_width=thin)]
    pts = rect_points(column_rect(grid, c))
    return [poly(pts, fill="#ffffff", stroke=COLORS["column"], stroke_width=sw),
            line(pts[0], pts[2], stroke=COLORS["column"], stroke_width=thin),
            line(pts[1], pts[3], stroke=COLORS["column"], stroke_width=thin)]


def area_and_centroid(points):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    a /= 2
    if abs(a) < 1e-9:
        return 0.0, points[0]
    return abs(a), (cx / (6 * a), cy / (6 * a))


def rect_points(d):
    x, y, w, h = (float(d[k]) for k in ("x", "y", "w", "d"))
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def bounds(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def floor_points(floor, walls):
    pts = []
    for w in walls.values():
        pts += w.quad(-w.ext_a, w.L + w.ext_b)
        for o in w.openings:
            if o["type"] == "door":
                hinge, leaf_end, jamb = door_geometry(w, o)
                pts += [leaf_end, add(leaf_end, sub(jamb, hinge))]
    for r in floor.get("rooms", []):
        pts += [tuple(p) for p in r.get("polygon", [])]
    for s in floor.get("stairs", []) + floor.get("fixtures", []):
        pts += rect_points(s)
    return pts


def door_geometry(w, o):
    """Hinge point, open leaf end and closing jamb of a door, on the wall face it swings to."""
    side = 1 if o.get("swing", "left") == "left" else -1
    if o.get("hinge", "start") == "start":
        s_hinge, toward = o["offset"], 1
    else:
        s_hinge, toward = o["offset"] + o["width"], -1
    face = w.t / 2 * side
    return (w.at(s_hinge, face), w.at(s_hinge, face + side * o["width"]),
            w.at(s_hinge + toward * o["width"], face))


def draw_door(w, o, k):
    out = []
    hinge, leaf_end, jamb = door_geometry(w, o)
    # sweep flag: positive-angle direction in SVG (y down) space
    ca, cb = sub(leaf_end, hinge), sub(jamb, hinge)
    cross = ca[0] * -cb[1] - (-ca[1]) * cb[0]
    sweep = 1 if cross > 0 else 0
    r = o["width"]
    out.append(line(hinge, leaf_end, stroke=COLORS["text"], stroke_width=f"{PAPER['line'] * k:.1f}"))
    out.append(f'<path d="M {pt(leaf_end)} A {r:.1f} {r:.1f} 0 0 {sweep} {pt(jamb)}" fill="none" '
               f'stroke="{COLORS["muted"]}" stroke-width="{PAPER["thin"] * k:.1f}"/>')
    return out


def draw_window(w, o, k):
    s0, s1, h = o["offset"], o["offset"] + o["width"], w.t / 2
    sw = f"{PAPER['thin'] * k:.1f}"
    return [poly(w.quad(s0, s1), fill="#ffffff", stroke=COLORS["window"], stroke_width=sw),
            line(w.at(s0), w.at(s1), stroke=COLORS["window"], stroke_width=sw),
            line(w.at(s0, -h / 3), w.at(s1, -h / 3), stroke=COLORS["window"], stroke_width=sw)]


def draw_stairs(s, k):
    out = []
    pts = rect_points(s)
    x0, y0, x1, y1 = bounds(pts)
    sw = f"{PAPER['thin'] * k:.1f}"
    out.append(poly(pts, fill="#ffffff", stroke=COLORS["text"], stroke_width=sw))
    up = s.get("up", "N").upper()
    steps = max(int(s.get("steps", 12)), 1)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if up in ("N", "S"):
        run = y1 - y0
        for i in range(1, steps):
            y = y0 + run * i / steps
            out.append(line((x0, y), (x1, y), stroke=COLORS["muted"], stroke_width=sw))
        start, end = ((cx, y0), (cx, y1)) if up == "N" else ((cx, y1), (cx, y0))
    else:
        run = x1 - x0
        for i in range(1, steps):
            x = x0 + run * i / steps
            out.append(line((x, y0), (x, y1), stroke=COLORS["muted"], stroke_width=sw))
        start, end = ((x0, cy), (x1, cy)) if up == "E" else ((x1, cy), (x0, cy))
    d = sub(end, start)
    u = mul(d, 1 / norm(d))
    n = (-u[1], u[0])
    inset = mul(u, run * 0.08)
    a, b = add(start, inset), sub(end, inset)
    ah = PAPER["text"] * k * 0.6
    out.append(line(a, b, stroke=COLORS["text"], stroke_width=f"{PAPER['line'] * k:.1f}"))
    out.append(poly([b, add(sub(b, mul(u, ah * 1.6)), mul(n, ah * 0.6)),
                     sub(sub(b, mul(u, ah * 1.6)), mul(n, ah * 0.6))], fill=COLORS["text"]))
    label_at = sub(a, mul(u, PAPER["small"] * k * 1.2))
    out.append(text((label_at[0], label_at[1] - PAPER["small"] * k / 3), s.get("label", "UP"),
                    PAPER["small"] * k, fill=COLORS["text"], font_weight="bold"))
    return out


def draw_room(r, k):
    out = []
    pts = [tuple(p) for p in r.get("polygon", [])]
    lines_ = [r.get("name", "")]
    anchor = tuple(r["label_at"]) if "label_at" in r else None
    if len(pts) >= 3:
        area, centroid = area_and_centroid(pts)
        anchor = anchor or centroid
        lines_.append(f"{area / 1e6:.1f} m²")
        x0, y0, x1, y1 = bounds(pts)
        if len(pts) == 4 and abs(area - (x1 - x0) * (y1 - y0)) < 1:
            lines_.append(f"{(x1 - x0) / 1000:.2f} × {(y1 - y0) / 1000:.2f} m")
    if anchor is None:
        return out
    size = PAPER["text"] * k
    top = anchor[1] + (len(lines_) - 1) * size * 0.6
    for i, s in enumerate(lines_):
        out.append(text((anchor[0], top - i * size * 1.2 - size * 0.35), s,
                        size if i == 0 else PAPER["small"] * k,
                        fill=COLORS["text"] if i == 0 else COLORS["muted"],
                        font_weight="bold" if i == 0 else "normal"))
    return out


def draw_dimension(a, b, offset_dir, label, k):
    """Dimension line from a to b, drawn offset_dir away, with tick marks and label."""
    sw = f"{PAPER['thin'] * k:.1f}"
    out = []
    pa, pb = add(a, offset_dir), add(b, offset_dir)
    out.append(line(pa, pb, stroke=COLORS["dim"], stroke_width=sw))
    on = mul(offset_dir, 1 / norm(offset_dir))
    for p, q in ((a, pa), (b, pb)):
        out.append(line(add(p, mul(on, PAPER["dim_gap"] * k * 0.2)), add(q, mul(on, PAPER["dim_gap"] * k * 0.25)),
                        stroke=COLORS["dim"], stroke_width=sw))
        t = PAPER["small"] * k * 0.5
        out.append(line((q[0] - t, q[1] - t), (q[0] + t, q[1] + t), stroke=COLORS["dim"],
                        stroke_width=f"{PAPER['line'] * k:.1f}"))
    mid = mul(add(pa, pb), 0.5)
    size = PAPER["small"] * k
    if abs(b[0] - a[0]) >= abs(b[1] - a[1]):
        out.append(text((mid[0], mid[1] + size * 0.4), label, size, fill=COLORS["dim"]))
    else:
        x, y = mid[0] - size * 0.4, -mid[1]
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" text-anchor="middle" '
                   f'fill="{COLORS["dim"]}" transform="rotate(-90 {x:.1f} {y:.1f})">{escape(label)}</text>')
    return out


def nice_bar(width):
    for v in (50000, 20000, 10000, 5000, 2000, 1000, 500):
        if v <= width / 3:
            return v
    return 500


def draw_floor(layout, floor, walls, frame, k, grid=None):
    fx0, fy0, fx1, fy1 = frame
    m, g, tb = PAPER["margin"] * k, PAPER["dim_gap"] * k, PAPER["title_block"] * k
    vx0, vy0 = fx0 - m - 2 * g, fy0 - m - 2 * g - tb
    extra = 2 * g + 2 * PAPER["bubble"] * k if grid else 0.0  # room for grid bubbles and spacings
    vx1, vy1 = fx1 + m + extra, fy1 + m + extra
    vw, vh = vx1 - vx0, vy1 - vy0
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{vw / k:.1f}mm" height="{vh / k:.1f}mm" '
           f'viewBox="{vx0:.1f} {-vy1:.1f} {vw:.1f} {vh:.1f}" font-family="Helvetica, Arial, sans-serif">',
           f'<title>{escape(layout.get("name", "Plan"))} — {escape(floor.get("name", "Floor " + str(floor["id"])))}</title>',
           f'<rect x="{vx0:.1f}" y="{-vy1:.1f}" width="{vw:.1f}" height="{vh:.1f}" fill="#ffffff"/>']

    if grid:
        out += draw_grid(grid, frame, k)
    out.append('<g id="fixtures">')
    for f in floor.get("fixtures", []):
        pts = rect_points(f)
        out.append(poly(pts, fill="none", stroke=COLORS["fixture"], stroke_width=f"{PAPER['thin'] * k:.1f}",
                        stroke_dasharray=f"{k:.1f} {k * 0.6:.1f}"))
        if f.get("label"):
            c = mul(add(pts[0], pts[2]), 0.5)
            out.append(text((c[0], c[1] - PAPER["small"] * k * 0.35), f["label"], PAPER["small"] * k * 0.85,
                            fill=COLORS["fixture"]))
    out.append('</g><g id="stairs">')
    for s in floor.get("stairs", []):
        out += draw_stairs(s, k)
    out.append('</g><g id="walls">')
    for w in walls.values():
        color = COLORS["exterior"] if w.type == "exterior" else COLORS["interior"]
        for s0, s1 in w.pieces():
            out.append(poly(w.quad(s0, s1), fill=color, stroke=color, stroke_width=f"{PAPER['thin'] * k * 0.5:.1f}"))
    columns = floor_columns(grid, floor)
    if columns:
        out.append('</g><g id="columns">')
        for _, _, c in columns:
            out += draw_column(grid, c, k)
    out.append('</g><g id="openings">')
    for w in walls.values():
        for o in w.openings:
            if o["type"] == "window":
                out += draw_window(w, o, k)
            elif o["type"] == "door":
                out += draw_door(w, o, k)
    out.append('</g><g id="rooms">')
    for r in floor.get("rooms", []):
        out += draw_room(r, k)
    out.append('</g>')

    # Overall outside dimensions of this floor (exterior walls, or all walls if none marked)
    dim_walls = [w for w in walls.values() if w.type == "exterior"] or list(walls.values())
    if dim_walls:
        pts = [p for w in dim_walls for p in w.quad(-w.ext_a, w.L + w.ext_b)]
        x0, y0, x1, y1 = bounds(pts)
        out.append('<g id="dimensions">')
        out += draw_dimension((x0, y0), (x1, y0), (0, fy0 - y0 - g * 1.2), metres(x1 - x0), k)
        out += draw_dimension((x0, y0), (x0, y1), (fx0 - x0 - g * 1.2, 0), metres(y1 - y0), k)
        out.append('</g>')

    # Title block, scale bar, north arrow
    size = PAPER["title"] * k
    ty = fy0 - 2 * g - size * 0.6
    out.append(text((fx0, ty), f'{layout.get("name", "")} — {floor.get("name", "Floor " + str(floor["id"]))}',
                    size, text_anchor="start", font_weight="bold", fill=COLORS["text"]))
    info = [f"Scale 1:{k:g}"]
    if "elevation" in floor:
        info.append(f"floor level {float(floor['elevation']) / 1000:+.2f} m")
    if "height" in floor:
        info.append(f"floor-to-floor {metres(float(floor['height']))}")
    rooms_area = sum(area_and_centroid([tuple(p) for p in r["polygon"]])[0]
                     for r in floor.get("rooms", []) if len(r.get("polygon", [])) >= 3)
    if rooms_area:
        info.append(f"room area {rooms_area / 1e6:.1f} m²")
    out.append(text((fx0, ty - size * 1.3), " · ".join(info), PAPER["small"] * k, text_anchor="start",
                    fill=COLORS["muted"]))
    bar = nice_bar(fx1 - fx0)
    bx, by, bh = fx1 - bar, ty - size * 0.2, PAPER["small"] * k * 0.6
    for i in range(4):
        out.append(f'<rect x="{bx + i * bar / 4:.1f}" y="{-by:.1f}" width="{bar / 4:.1f}" height="{bh:.1f}" '
                   f'fill="{COLORS["text"] if i % 2 == 0 else "#ffffff"}" stroke="{COLORS["text"]}" '
                   f'stroke-width="{PAPER["thin"] * k:.1f}"/>')
    for x, s in ((bx, "0"), (bx + bar, f"{bar / 1000:g} m")):
        out.append(text((x, by - bh - PAPER["small"] * k * 1.1), s, PAPER["small"] * k, fill=COLORS["muted"]))
    if "north" in layout:
        r = size * 0.9
        nx, ny = bx - r * 3, ty - size * 0.3
        out.append(f'<g transform="rotate({float(layout["north"]):.1f} {nx:.1f} {-ny:.1f})">'
                   + poly([(nx, ny + r), (nx + r * 0.45, ny - r), (nx, ny - r * 0.5), (nx - r * 0.45, ny - r)],
                          fill=COLORS["text"])
                   + text((nx, ny + r * 1.25), "N", PAPER["small"] * k, font_weight="bold", fill=COLORS["text"])
                   + '</g>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", type=Path)
    ap.add_argument("--out", type=Path, help="output folder (default: the layout's folder)")
    args = ap.parse_args()
    try:
        layout = json.loads(args.layout.read_text(encoding="utf-8"))
        if layout.get("units", "mm") != "mm":
            raise LayoutError('layout "units" must be "mm"')
        floors = layout.get("floors") or []
        if not floors:
            raise LayoutError("layout has no floors")
        k = float(layout.get("scale", 50))
        grid = parse_grid(layout.get("grid"))
        built, all_pts = [], grid_points(grid) if grid else []
        for f in floors:
            if "id" not in f:
                raise LayoutError(f"floor {f.get('name', '?')!r} has no id")
            walls = build_walls(f)
            built.append((f, walls))
            all_pts += floor_points(f, walls)
            for _, _, c in floor_columns(grid, f):
                all_pts += rect_points(column_rect(grid, c))
        if not all_pts:
            raise LayoutError("layout has no geometry")
        frame = bounds(all_pts)
    except (LayoutError, KeyError, ValueError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out_dir = args.out or args.layout.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for f, walls in built:
        path = out_dir / f"floor-{f['id']}.svg"
        path.write_text(draw_floor(layout, f, walls, frame, k, grid), encoding="utf-8")
        print(f"{path}  ({f.get('name', '')})")
        columns = floor_columns(grid, f)
        if columns:
            print(f"    {'columns':<24} {len(columns):6d}")
        total = 0.0
        for r in f.get("rooms", []):
            if len(r.get("polygon", [])) >= 3:
                a = area_and_centroid([tuple(p) for p in r["polygon"]])[0] / 1e6
                total += a
                print(f"    {r.get('name', '?'):<24} {a:6.1f} m²")
        if total:
            print(f"    {'total':<24} {total:6.1f} m²")
    return 0


if __name__ == "__main__":
    sys.exit(main())
