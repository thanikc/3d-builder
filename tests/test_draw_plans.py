"""Unit tests for skills/3d-builder/scripts/draw_plans.py.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "3d-builder"
SCRIPT = SKILL / "scripts" / "draw_plans.py"

_spec = importlib.util.spec_from_file_location("draw_plans", SCRIPT)
dp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dp)

SVG_NS = "{http://www.w3.org/2000/svg}"


def box_floor(fid="0", w=6000, d=4000, t=200, **extra):
    """A rectangular floor of four exterior walls, corners sharing endpoints."""
    floor = {
        "id": fid,
        "name": f"Floor {fid}",
        "walls": [
            {"id": "s", "from": [0, 0], "to": [w, 0], "thickness": t, "type": "exterior"},
            {"id": "e", "from": [w, 0], "to": [w, d], "thickness": t, "type": "exterior"},
            {"id": "n", "from": [w, d], "to": [0, d], "thickness": t, "type": "exterior"},
            {"id": "w", "from": [0, d], "to": [0, 0], "thickness": t, "type": "exterior"},
        ],
    }
    floor.update(extra)
    return floor


def run_main(*argv):
    """Run draw_plans.main() in-process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["draw_plans.py", *map(str, argv)]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = dp.main()
    return code, out.getvalue(), err.getvalue()


class GeometryHelpers(unittest.TestCase):
    def test_vector_ops(self):
        self.assertEqual(dp.add((1, 2), (3, 4)), (4, 6))
        self.assertEqual(dp.sub((1, 2), (3, 5)), (-2, -3))
        self.assertEqual(dp.mul((1, -2), 3), (3, -6))
        self.assertEqual(dp.norm((3, 4)), 5)

    def test_close_uses_eps(self):
        self.assertTrue(dp.close((0, 0), (0.5, 0)))
        self.assertFalse(dp.close((0, 0), (1.5, 0)))

    def test_pt_flips_y_for_svg(self):
        self.assertEqual(dp.pt((10, 20)), "10.0,-20.0")

    def test_metres(self):
        self.assertEqual(dp.metres(9300), "9.30 m")

    def test_fmt_attrs_turns_underscores_into_hyphens(self):
        self.assertEqual(dp.fmt_attrs({"stroke_width": "1", "fill": "red"}),
                         ' stroke-width="1" fill="red"')

    def test_text_escapes_content(self):
        self.assertIn("A &amp; B &lt;x&gt;", dp.text((0, 0), "A & B <x>", 2))

    def test_nice_bar_is_at_most_a_third_of_the_width(self):
        self.assertEqual(dp.nice_bar(9000), 2000)
        self.assertEqual(dp.nice_bar(30000), 10000)
        self.assertEqual(dp.nice_bar(100), 500)  # floor value for tiny plans

    def test_rect_points_and_bounds(self):
        pts = dp.rect_points({"x": 1, "y": 2, "w": 10, "d": 5})
        self.assertEqual(pts, [(1, 2), (11, 2), (11, 7), (1, 7)])
        self.assertEqual(dp.bounds(pts), (1, 2, 11, 7))


class AreaAndCentroid(unittest.TestCase):
    def test_rectangle(self):
        area, c = dp.area_and_centroid([(0, 0), (4000, 0), (4000, 3000), (0, 3000)])
        self.assertAlmostEqual(area, 12e6)
        self.assertAlmostEqual(c[0], 2000)
        self.assertAlmostEqual(c[1], 1500)

    def test_clockwise_order_still_gives_positive_area(self):
        area, c = dp.area_and_centroid([(0, 0), (0, 3000), (4000, 3000), (4000, 0)])
        self.assertAlmostEqual(area, 12e6)
        self.assertAlmostEqual(c[0], 2000)

    def test_l_shape(self):
        # 2x2 square with the top-right 1x1 removed: area 3
        area, _ = dp.area_and_centroid([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
        self.assertAlmostEqual(area, 3)

    def test_degenerate_polygon(self):
        area, c = dp.area_and_centroid([(0, 0), (1, 0), (2, 0)])
        self.assertEqual(area, 0.0)
        self.assertEqual(c, (0, 0))


class WallTests(unittest.TestCase):
    def test_defaults(self):
        w = dp.Wall({"id": 1, "from": [0, 0], "to": [3000, 0]})
        self.assertEqual(w.id, "1")
        self.assertEqual(w.t, 200)
        self.assertEqual(w.type, "interior")
        self.assertEqual(w.L, 3000)

    def test_direction_and_left_normal(self):
        w = dp.Wall({"id": "a", "from": [0, 0], "to": [0, 2000]})
        self.assertEqual(w.u, (0, 1))
        self.assertEqual(w.n, (-1, 0))  # left of a northward wall is west
        self.assertEqual(w.at(500, 100), (-100, 500))

    def test_quad_spans_thickness(self):
        w = dp.Wall({"id": "a", "from": [0, 0], "to": [1000, 0], "thickness": 300})
        self.assertEqual(dp.bounds(w.quad(0, 1000)), (0, -150, 1000, 150))

    def test_missing_key_raises(self):
        with self.assertRaisesRegex(dp.LayoutError, "missing"):
            dp.Wall({"id": "a", "from": [0, 0]})

    def test_zero_length_raises(self):
        with self.assertRaisesRegex(dp.LayoutError, "zero length"):
            dp.Wall({"id": "a", "from": [5, 5], "to": [5.5, 5]})

    def test_pieces_skip_openings(self):
        w = dp.Wall({"id": "a", "from": [0, 0], "to": [5000, 0]})
        w.openings = [{"offset": 1000, "width": 900}, {"offset": 3000, "width": 1200}]
        self.assertEqual(w.pieces(), [(0.0, 1000), (1900, 3000), (4200, 5000)])

    def test_pieces_include_corner_extensions(self):
        w = dp.Wall({"id": "a", "from": [0, 0], "to": [5000, 0]})
        w.ext_a, w.ext_b = 100, 60
        self.assertEqual(w.pieces(), [(-100, 5060)])

    def test_pieces_with_opening_at_wall_end(self):
        w = dp.Wall({"id": "a", "from": [0, 0], "to": [5000, 0]})
        w.openings = [{"offset": 0, "width": 1000}, {"offset": 4000, "width": 1000}]
        self.assertEqual(w.pieces(), [(1000, 4000)])


class BuildWalls(unittest.TestCase):
    def test_corners_extend_by_half_the_other_wall(self):
        floor = box_floor()
        floor["walls"][1]["thickness"] = 300  # east wall thicker
        walls = dp.build_walls(floor)
        self.assertEqual(walls["s"].ext_a, 100)  # meets west wall (200)
        self.assertEqual(walls["s"].ext_b, 150)  # meets east wall (300)
        self.assertEqual(walls["e"].ext_a, 100)

    def test_free_end_and_t_junction_are_not_extended(self):
        floor = box_floor()
        # interior wall ending on the south wall's centreline (T-junction), free at the top
        floor["walls"].append({"id": "i", "from": [3000, 0], "to": [3000, 2000], "thickness": 100})
        walls = dp.build_walls(floor)
        self.assertEqual((walls["i"].ext_a, walls["i"].ext_b), (0, 0))

    def test_duplicate_wall_id(self):
        floor = box_floor()
        floor["walls"][1]["id"] = "s"
        with self.assertRaisesRegex(dp.LayoutError, "duplicate wall id s"):
            dp.build_walls(floor)

    def test_opening_on_unknown_wall(self):
        floor = box_floor(openings=[{"wall": "x", "offset": 0, "width": 900}])
        with self.assertRaisesRegex(dp.LayoutError, "unknown wall 'x'"):
            dp.build_walls(floor)

    def test_opening_too_wide_for_wall(self):
        floor = box_floor(openings=[{"wall": "s", "offset": 5500, "width": 900}])
        with self.assertRaisesRegex(dp.LayoutError, "does not fit"):
            dp.build_walls(floor)

    def test_negative_offset(self):
        floor = box_floor(openings=[{"wall": "s", "offset": -10, "width": 900}])
        with self.assertRaisesRegex(dp.LayoutError, "does not fit"):
            dp.build_walls(floor)

    def test_opening_exactly_filling_wall_is_allowed(self):
        floor = box_floor(openings=[{"wall": "s", "offset": 0, "width": 6000, "type": "opening"}])
        walls = dp.build_walls(floor)
        self.assertEqual(len(walls["s"].openings), 1)

    def test_overlapping_openings(self):
        floor = box_floor(openings=[{"wall": "s", "offset": 1000, "width": 1000},
                                    {"wall": "s", "offset": 1500, "width": 900}])
        with self.assertRaisesRegex(dp.LayoutError, "overlap on wall s"):
            dp.build_walls(floor)

    def test_adjacent_openings_do_not_overlap(self):
        floor = box_floor(openings=[{"wall": "s", "offset": 1000, "width": 1000},
                                    {"wall": "s", "offset": 2000, "width": 900}])
        dp.build_walls(floor)

    def test_openings_sorted_and_default_to_door(self):
        floor = box_floor(openings=[{"wall": "s", "offset": "3000", "width": 900},
                                    {"wall": "s", "offset": 500, "width": "1200", "type": "window"}])
        walls = dp.build_walls(floor)
        self.assertEqual([o["offset"] for o in walls["s"].openings], [500.0, 3000.0])
        self.assertEqual([o["type"] for o in walls["s"].openings], ["window", "door"])


class DoorGeometry(unittest.TestCase):
    def setUp(self):
        self.w = dp.Wall({"id": "s", "from": [0, 0], "to": [5000, 0], "thickness": 200})

    def geom(self, **o):
        return dp.door_geometry(self.w, dict({"offset": 1000, "width": 900}, **o))

    def test_hinge_start_swing_left(self):
        hinge, leaf, jamb = self.geom()
        self.assertEqual(hinge, (1000, 100))
        self.assertEqual(leaf, (1000, 1000))
        self.assertEqual(jamb, (1900, 100))

    def test_hinge_end_swing_right(self):
        hinge, leaf, jamb = self.geom(hinge="end", swing="right")
        self.assertEqual(hinge, (1900, -100))
        self.assertEqual(leaf, (1900, -1000))
        self.assertEqual(jamb, (1000, -100))

    def test_door_swing_is_included_in_frame(self):
        floor = box_floor(openings=[{"wall": "s", "offset": 1000, "width": 900, "swing": "right"}])
        walls = dp.build_walls(floor)
        _, y0, _, _ = dp.bounds(dp.floor_points(floor, walls))
        self.assertAlmostEqual(y0, -1000)  # leaf swings 900 mm outside the 100 mm wall face


class DrawRoom(unittest.TestCase):
    def texts(self, items):
        """Visible label text, skipping the white halo copies drawn underneath."""
        return [re.sub("<[^>]+>", "", s) for s in items if 'stroke="#ffffff"' not in s]

    def test_labels_get_a_white_halo_drawn_first(self):
        room = {"name": "Living", "polygon": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]]}
        items = dp.draw_room(room, 50)
        self.assertEqual(len(items), 6)
        self.assertTrue(all('stroke="#ffffff"' in s for s in items[:3]))
        self.assertFalse(any("stroke=" in s for s in items[3:]))
        self.assertEqual([re.sub("<[^>]+>", "", s) for s in items[:3]],
                         [re.sub("<[^>]+>", "", s) for s in items[3:]])

    def test_rectangle_gets_name_area_and_size(self):
        room = {"name": "Living", "polygon": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]]}
        self.assertEqual(self.texts(dp.draw_room(room, 50)),
                         ["Living", "20.0 m²", "5.00 × 4.00 m"])

    def test_l_shape_has_no_size_line(self):
        room = {"name": "Hall", "polygon": [[0, 0], [2000, 0], [2000, 1000], [1000, 1000],
                                            [1000, 2000], [0, 2000]]}
        self.assertEqual(self.texts(dp.draw_room(room, 50)), ["Hall", "3.0 m²"])

    def test_label_at_overrides_centroid(self):
        room = {"name": "X", "label_at": [123, 456], "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}
        self.assertIn('x="123.0"', dp.draw_room(room, 50)[0])

    def test_no_polygon_and_no_label_draws_nothing(self):
        self.assertEqual(dp.draw_room({"name": "Ghost"}, 50), [])

    def test_label_without_polygon(self):
        self.assertEqual(self.texts(dp.draw_room({"name": "Void", "label_at": [0, 0]}, 50)), ["Void"])


class DrawFloor(unittest.TestCase):
    def render(self, layout, floor):
        walls = dp.build_walls(floor)
        frame = dp.bounds(dp.floor_points(floor, walls))
        k = float(layout.get("scale", 50))
        return dp.draw_floor(layout, floor, walls, frame, k)

    def test_output_is_valid_svg_with_all_groups(self):
        floor = box_floor(
            openings=[{"wall": "s", "type": "door", "offset": 1000, "width": 900},
                      {"wall": "n", "type": "window", "offset": 1000, "width": 1500},
                      {"wall": "e", "type": "opening", "offset": 1000, "width": 1000}],
            rooms=[{"name": "Room", "polygon": [[100, 100], [5900, 100], [5900, 3900], [100, 3900]]}],
            stairs=[{"x": 4000, "y": 500, "w": 1000, "d": 2500, "up": "N"}],
            fixtures=[{"label": "counter", "x": 200, "y": 3200, "w": 2000, "d": 600}])
        root = ET.fromstring(self.render({"name": "Test", "scale": 50}, floor))
        self.assertEqual(root.tag, SVG_NS + "svg")
        groups = {g.get("id") for g in root.iter(SVG_NS + "g")}
        self.assertTrue({"fills", "fixtures", "furniture", "stairs", "walls", "openings",
                         "rooms", "dimensions"} <= groups)

    def test_paper_size_follows_scale(self):
        root = ET.fromstring(self.render({"scale": 100}, box_floor()))
        _, _, vw, vh = map(float, root.get("viewBox").split())
        self.assertAlmostEqual(float(root.get("width")[:-2]), vw / 100, places=0)
        self.assertAlmostEqual(float(root.get("height")[:-2]), vh / 100, places=0)

    def test_overall_dimensions_measured_over_outer_faces(self):
        svg = self.render({}, box_floor(w=6000, d=4000, t=200))
        self.assertIn(">6.20 m<", svg)
        self.assertIn(">4.20 m<", svg)

    def test_window_does_not_break_wall_into_door_swing(self):
        floor = box_floor(openings=[{"wall": "s", "type": "window", "offset": 1000, "width": 1500}])
        svg = self.render({}, floor)
        self.assertNotIn("<path", svg)  # door arcs are the only paths

    def test_door_draws_arc(self):
        floor = box_floor(openings=[{"wall": "s", "type": "door", "offset": 1000, "width": 900}])
        self.assertEqual(self.render({}, floor).count("<path"), 1)

    def test_door_swing_flag_flips_with_swing_side(self):
        def sweep(swing):
            floor = box_floor(openings=[{"wall": "s", "offset": 1000, "width": 900, "swing": swing}])
            return re.search(r" A [\d.]+ [\d.]+ 0 0 (\d)", self.render({}, floor)).group(1)
        self.assertNotEqual(sweep("left"), sweep("right"))

    def test_title_and_info_line(self):
        floor = box_floor(elevation=2900, height=2800,
                          rooms=[{"name": "A", "polygon": [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]}])
        svg = self.render({"name": "Tom & Jerry's", "scale": 50}, floor)
        self.assertIn("<title>Tom &amp; Jerry's — Floor 0</title>", svg)
        self.assertIn("Scale 1:50", svg)
        self.assertIn("floor level +2.90 m", svg)
        self.assertIn("floor-to-floor 2.80 m", svg)
        self.assertIn("room area 6.0 m²", svg)
        ET.fromstring(svg)

    def test_north_arrow_only_when_given(self):
        self.assertNotIn(">N</text>", self.render({}, box_floor()))
        svg = self.render({"north": 30}, box_floor())
        self.assertIn(">N</text>", svg)
        self.assertIn("rotate(30.0", svg)

    def test_stair_directions(self):
        for up in "NSEW":
            floor = box_floor(stairs=[{"x": 1000, "y": 1000, "w": 1000, "d": 2000, "up": up,
                                       "steps": 10, "label": "UP"}])
            svg = self.render({}, floor)
            stairs = re.search(r'<g id="stairs">(.*?)</g>', svg, re.S).group(1)
            # 9 tread lines + arrow shaft
            self.assertEqual(stairs.count("<line"), 10, up)
            self.assertIn(">UP<", stairs)

    def test_interior_walls_used_for_dimensions_when_no_exterior(self):
        floor = {"id": "0", "walls": [{"id": "a", "from": [0, 0], "to": [3000, 0], "thickness": 100}]}
        self.assertIn(">3.00 m<", self.render({}, floor))


class MainCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, layout, name="layout.json"):
        p = self.dir / name
        p.write_text(json.dumps(layout) if not isinstance(layout, str) else layout, encoding="utf-8")
        return p

    def two_floor_layout(self):
        room = {"name": "Big room", "polygon": [[100, 100], [5900, 100], [5900, 3900], [100, 3900]]}
        ground = box_floor("0", rooms=[room],
                           stairs=[{"x": 4500, "y": 200, "w": 1000, "d": 3000, "up": "N", "label": "UP"}])
        upper = box_floor("1", w=8000, rooms=[dict(room, name="Loft")])
        return {"name": "House", "units": "mm", "floors": [ground, upper]}

    def test_writes_one_svg_per_floor_next_to_layout(self):
        code, out, err = run_main(self.write(self.two_floor_layout()))
        self.assertEqual(code, 0, err)
        self.assertTrue((self.dir / "floor-0.svg").is_file())
        self.assertTrue((self.dir / "floor-1.svg").is_file())
        self.assertIn("Big room", out)
        self.assertIn("22.0 m²", out)
        self.assertIn("total", out)

    def test_floors_share_one_frame(self):
        run_main(self.write(self.two_floor_layout()))
        boxes = {ET.parse(self.dir / f"floor-{i}.svg").getroot().get("viewBox") for i in "01"}
        self.assertEqual(len(boxes), 1)

    def test_out_dir_is_created(self):
        out_dir = self.dir / "a" / "b"
        code, _, err = run_main(self.write(self.two_floor_layout()), "--out", out_dir)
        self.assertEqual(code, 0, err)
        self.assertTrue((out_dir / "floor-1.svg").is_file())
        self.assertFalse((self.dir / "floor-1.svg").exists())

    def test_floor_id_names_the_file(self):
        layout = {"floors": [box_floor("b1")]}
        run_main(self.write(layout))
        self.assertTrue((self.dir / "floor-b1.svg").is_file())

    def assert_error(self, layout, message):
        code, out, err = run_main(self.write(layout))
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertEqual(list(self.dir.glob("*.svg")), [])

    def test_rejects_non_mm_units(self):
        self.assert_error({"units": "m", "floors": [box_floor()]}, '"units" must be "mm"')

    def test_rejects_missing_floors(self):
        self.assert_error({"floors": []}, "no floors")

    def test_rejects_floor_without_id(self):
        floor = box_floor()
        del floor["id"]
        self.assert_error({"floors": [floor]}, "has no id")

    def test_rejects_empty_geometry(self):
        self.assert_error({"floors": [{"id": "0"}]}, "no geometry")

    def test_rejects_invalid_json(self):
        self.assert_error("{not json", "error:")

    def test_layout_errors_are_reported_not_raised(self):
        self.assert_error({"floors": [box_floor(openings=[{"wall": "zz", "offset": 0, "width": 1}])]},
                          "unknown wall")

    def test_errors_in_later_floor_write_nothing(self):
        bad = box_floor("1", openings=[{"wall": "s", "offset": 0, "width": 99999}])
        self.assert_error({"floors": [box_floor("0"), bad]}, "does not fit")


class GridTests(unittest.TestCase):
    GRID = {"x": [0, 3000, 6000], "y": [0, 4000], "columns": "all"}

    def render(self, grid_spec, floor=None):
        floor = floor or box_floor()
        grid = dp.parse_grid(grid_spec)
        walls = dp.build_walls(floor)
        frame = dp.bounds(dp.floor_points(floor, walls) + dp.grid_points(grid))
        return ET.fromstring(dp.draw_floor({}, floor, walls, frame, 50, grid))

    def test_default_labels(self):
        self.assertEqual(dp.grid_labels(3, False), ["1", "2", "3"])
        self.assertEqual(dp.grid_labels(28, True)[:3], ["A", "B", "C"])
        self.assertEqual(dp.grid_labels(28, True)[-2:], ["AA", "AB"])

    def test_parse_grid_defaults(self):
        g = dp.parse_grid(self.GRID)
        self.assertEqual(g["x"], [("1", 0), ("2", 3000), ("3", 6000)])
        self.assertEqual(g["y"], [("A", 0), ("B", 4000)])
        self.assertEqual(g["column"], {"shape": "square", "w": 300, "d": 300})
        self.assertEqual(len(g["columns"]), 6)
        self.assertIsNone(dp.parse_grid(None))

    def test_custom_labels_and_round_columns(self):
        g = dp.parse_grid({"x": [0, 5000], "x_labels": ["G1", "G2"], "y": [0],
                           "column": {"diameter": 250}, "columns": [["G2", "A"]]})
        self.assertEqual(g["columns"], [("G2", "A", (5000, 0))])
        self.assertEqual(g["column"]["shape"], "round")

    def test_parse_grid_errors(self):
        cases = [({"x": [0, 0]}, "increasing"),
                 ({"x": [0, 1000], "x_labels": ["1"]}, "x_labels"),
                 ({"x": [0], "y": [0], "x_labels": ["A"]}, "duplicate grid labels A"),
                 ({"x": [], "y": []}, "no x or y lines"),
                 ({"x": [0], "y": [0], "columns": [["9", "A"]]}, "unknown grid line"),
                 ({"x": [0], "y": [0], "columns": ["1A"]}, "must be"),
                 ({"x": [0], "y": [0], "columns": [["1", "A", 400]]}, "must be")]
        for spec, msg in cases:
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(dp.LayoutError, msg):
                    dp.parse_grid(spec)

    def test_column_with_its_own_size(self):
        g = dp.parse_grid({"x": [0, 6000], "y": [0], "columns": [["1", "A"], ["2", "A", 400, "600"]]})
        self.assertEqual(g["columns"], [("1", "A", (0, 0)), ("2", "A", (6000, 0, 400.0, 600.0))])
        self.assertEqual(dp.column_rect(g, g["columns"][0][2]), {"x": -150, "y": -150, "w": 300, "d": 300})
        self.assertEqual(dp.column_rect(g, g["columns"][1][2]), {"x": 5800, "y": -300, "w": 400, "d": 600})
        self.assertIn((6200, 300), dp.grid_points(g))  # frame reaches the bigger column
        on_floor = dp.floor_columns(g, {"id": "1", "columns": [["2", "A", 500, 500]]})
        self.assertEqual(on_floor, [("2", "A", (6000, 0, 500.0, 500.0))])

    def test_sized_columns_are_drawn_at_their_size(self):
        root = self.render({"x": [0, 6000], "y": [0], "columns": [["1", "A"], ["2", "A", 400, 600]]})
        groups = {g.get("id"): g for g in root.iter(SVG_NS + "g")}
        sizes = []
        for poly in groups["columns"].findall(SVG_NS + "polygon"):
            pts = [tuple(map(float, xy.split(","))) for xy in poly.get("points").split()]
            xs, ys = [x for x, _ in pts], [y for _, y in pts]
            sizes.append((round(max(xs) - min(xs)), round(max(ys) - min(ys))))
        self.assertEqual(sorted(sizes), [(300, 300), (400, 600)])

        root = self.render({"x": [0, 6000], "y": [0], "column": {"diameter": 250},
                            "columns": [["1", "A"], ["2", "A", 500, 500]]})
        groups = {g.get("id"): g for g in root.iter(SVG_NS + "g")}
        radii = sorted(float(c.get("r")) for c in groups["columns"].findall(SVG_NS + "circle"))
        self.assertEqual(radii, [125, 250])

    def test_draws_lines_bubbles_spacings_and_columns(self):
        root = self.render(self.GRID)
        groups = {g.get("id"): g for g in root.iter(SVG_NS + "g")}
        grid = groups["grid"]
        self.assertEqual(len(grid.findall(SVG_NS + "circle")), 5)
        labels = {t.text for t in grid.iter(SVG_NS + "text")}
        self.assertTrue({"1", "2", "3", "A", "B", "3.00 m", "4.00 m"} <= labels)
        self.assertEqual(len(groups["columns"].findall(SVG_NS + "polygon")), 6)

    def test_grid_widens_sheet(self):
        plain = ET.fromstring(DrawFloor().render({}, box_floor()))
        with_grid = self.render({"x": [0, 6000], "y": [0, 4000]})
        w = lambda r: float(r.get("viewBox").split()[2])
        self.assertGreater(w(with_grid), w(plain))
        self.assertNotIn("columns", {g.get("id") for g in with_grid.iter(SVG_NS + "g")})

    def test_floor_overrides_columns(self):
        g = dp.parse_grid(self.GRID)
        self.assertEqual(len(dp.floor_columns(g, {"id": "1"})), 6)
        self.assertEqual(dp.floor_columns(g, {"id": "1", "columns": []}), [])
        self.assertEqual(len(dp.floor_columns(g, {"id": "1", "columns": [["1", "A"]]})), 1)
        with self.assertRaisesRegex(dp.LayoutError, "no grid"):
            dp.floor_columns(None, {"id": "1", "columns": "all"})

    def test_cli_draws_grid_on_every_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "layout.json"
            p.write_text(json.dumps({"grid": self.GRID, "floors": [
                box_floor("0"), box_floor("1", columns=[["2", "B"]])]}), encoding="utf-8")
            code, out, err = run_main(p)
            self.assertEqual(code, 0, err)
            self.assertIn("columns                       6", out)
            self.assertIn("columns                       1", out)
            for fid in "01":
                root = ET.parse(Path(tmp) / f"floor-{fid}.svg").getroot()
                self.assertIn("grid", {g.get("id") for g in root.iter(SVG_NS + "g")})

    def test_cli_reports_grid_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "layout.json"
            p.write_text(json.dumps({"grid": {"x": [5, 1]}, "floors": [box_floor()]}), encoding="utf-8")
            code, _, err = run_main(p)
            self.assertEqual(code, 1)
            self.assertIn("increasing", err)


fu = dp.furniture  # sibling module imported by draw_plans.py


def apply_matrix(transform, u, v):
    """Map local (u, v) through an SVG matrix(...) string, back to plan coords (y up)."""
    a, b, c, d, e, f = map(float, re.findall(r"-?[\d.]+", transform))
    return (a * u + c * v + e, -(b * u + d * v + f))


class FurnitureSymbols(unittest.TestCase):
    PIECE = {"x": 1000, "y": 2000, "w": 2000, "d": 1000}

    def test_documented_types_match_symbols(self):
        md = (SKILL / "references" / "floorplans.md").read_text(encoding="utf-8")
        types = re.search(r"Types: `([^`]+)`", md).group(1).split()
        self.assertEqual(sorted(types), sorted(fu.SYMBOLS))

    def test_every_symbol_renders_valid_svg_in_every_facing(self):
        for kind in fu.SYMBOLS:
            for facing in "NESW":
                with self.subTest(kind=kind, facing=facing):
                    it = dict(self.PIECE, type=kind, facing=facing, label="A & B")
                    svg = ('<svg xmlns="http://www.w3.org/2000/svg">'
                           + "".join(fu.draw_item(it, 50, 0.13)) + "</svg>")
                    root = ET.fromstring(svg)
                    self.assertGreater(len(list(root.iter())), 2)

    def test_local_size_swaps_for_east_and_west(self):
        self.assertEqual(fu.local_size(dict(self.PIECE, facing="S")), (2000, 1000))
        self.assertEqual(fu.local_size(dict(self.PIECE, facing="n")), (2000, 1000))
        self.assertEqual(fu.local_size(dict(self.PIECE, facing="E")), (1000, 2000))
        self.assertEqual(fu.local_size(dict(self.PIECE, facing="W")), (1000, 2000))
        self.assertEqual(fu.local_size(self.PIECE), (2000, 1000))  # default S

    def test_transform_fills_footprint_and_front_points_the_right_way(self):
        x0, y0, x1, y1 = 1000, 2000, 3000, 3000
        fronts = {"S": (2000, 2000), "N": (2000, 3000), "E": (3000, 2500), "W": (1000, 2500)}
        for facing, front in fronts.items():
            with self.subTest(facing=facing):
                it = dict(self.PIECE, facing=facing)
                W, D = fu.local_size(it)
                m = fu.transform(it)
                corners = [apply_matrix(m, u, v) for u, v in ((0, 0), (W, 0), (W, D), (0, D))]
                self.assertEqual(dp.bounds(corners), (x0, y0, x1, y1))
                fx, fy = apply_matrix(m, W / 2, 0)
                self.assertAlmostEqual(fx, front[0])
                self.assertAlmostEqual(fy, front[1])

    def test_unknown_type_and_bad_facing_raise(self):
        with self.assertRaisesRegex(ValueError, "unknown furniture type 'throne'"):
            fu.draw_item(dict(self.PIECE, type="throne"), 50, 0.13)
        with self.assertRaisesRegex(ValueError, "facing"):
            fu.draw_item(dict(self.PIECE, type="bed", facing="NE"), 50, 0.13)

    def test_label_is_escaped_and_centred(self):
        out = fu.draw_item(dict(self.PIECE, type="cabinet", label="A & B"), 50, 0.13)
        self.assertIn(">A &amp; B</text>", out[-1])
        self.assertIn('x="2000.0"', out[-1])
        self.assertNotIn("<text", "".join(fu.draw_item(dict(self.PIECE, type="cabinet"), 50, 0.13)))

    def test_options_change_the_drawing(self):
        def count(kind, tag, **opts):
            return "".join(fu.draw_item(dict(self.PIECE, type=kind, **opts), 50, 0.13)).count(tag)
        self.assertEqual(count("table", "<polygon"), 0)
        self.assertEqual(count("table", "<polygon", seats=6), 12)  # 2 polygons per chair
        self.assertEqual(count("table", "<polygon", seats=6, ends=True), 12)
        self.assertEqual(count("round_table", "<polygon", seats=4), 8)
        self.assertGreater(count("sink", "<rect", bowls=2), count("sink", "<rect"))
        self.assertNotEqual(fu.draw_item(dict(self.PIECE, type="hob", burners=2), 50, 0.13),
                            fu.draw_item(dict(self.PIECE, type="hob"), 50, 0.13))
        self.assertGreater(count("basin", "<ellipse", basins=2), count("basin", "<ellipse"))
        self.assertEqual(count("basin", "<ellipse", trough=True), 0)  # one long bowl, not round ones
        self.assertEqual(count("basin", "<ellipse", trough=True, basins=2), 0)
        self.assertEqual(count("basin", "<rect", trough=True), 2)
        self.assertEqual(count("basin", "<circle", trough=True), 1)  # single tap
        self.assertLess(count("desk", "<circle", chair=False), count("desk", "<circle"))
        self.assertGreater(count("desk", "<rect", speakers=True), count("desk", "<rect"))
        self.assertEqual(count("desk", "<rect", monitor=False), count("desk", "<rect") - 1)  # no screen
        self.assertEqual(count("desk", "<rect", monitor=False, speakers=True),
                         count("desk", "<rect", speakers=True) - 1)
        self.assertNotIn("#555555", "".join(fu.draw_item(dict(self.PIECE, type="desk", monitor=False), 50, 0.13)))
        self.assertEqual(count("wardrobe", "stroke-dasharray", doors="mirror"), 0)  # no hanging rail
        self.assertGreater(count("wardrobe", "stroke-dasharray"), 0)
        self.assertEqual(count("wardrobe", "<rect", doors="mirror"), 2)  # carcass and door panel
        self.assertGreater(count("wardrobe", "<line", doors="mirror"), 4)  # leaf split and hatching
        self.assertGreater(count("appliance", "<circle", drum=True), count("appliance", "<circle"))
        self.assertNotEqual(
            "".join(fu.draw_item(dict(self.PIECE, d=2000, type="sofa_l", return_side="left"), 50, 0.13)),
            "".join(fu.draw_item(dict(self.PIECE, d=2000, type="sofa_l", return_side="right"), 50, 0.13)))


class FurnitureInPlans(unittest.TestCase):
    BED = {"type": "bed", "x": 1000, "y": 1000, "w": 1600, "d": 2000, "facing": "S"}

    def test_floor_draws_furniture_group_above_fixtures_below_stairs(self):
        floor = box_floor(furniture=[self.BED], fixtures=[{"x": 0, "y": 0, "w": 100, "d": 100}],
                          stairs=[{"x": 4000, "y": 500, "w": 1000, "d": 2500, "up": "N"}])
        svg = DrawFloor().render({}, floor)
        ET.fromstring(svg)
        group = re.search(r'<g id="furniture">(.*?)</g><g id="stairs">', svg, re.S).group(1)
        self.assertIn("matrix(", group)
        self.assertLess(svg.index('id="fixtures"'), svg.index('id="furniture"'))

    def test_furniture_extends_the_frame(self):
        floor = box_floor(furniture=[dict(self.BED, type="car", x=-4000, y=-6000, w=1800, d=4500)])
        walls = dp.build_walls(floor)
        x0, y0, _, _ = dp.bounds(dp.floor_points(floor, walls))
        self.assertEqual((x0, y0), (-4000, -6000))

    def run_layout(self, furniture):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "layout.json"
            p.write_text(json.dumps({"floors": [box_floor(furniture=furniture)]}), encoding="utf-8")
            code, out, err = run_main(p)
            svgs = list(Path(tmp).glob("*.svg"))
            return code, err, svgs

    def test_cli_renders_furniture(self):
        code, err, svgs = self.run_layout([self.BED, dict(self.BED, type="wardrobe", facing="e")])
        self.assertEqual(code, 0, err)
        self.assertEqual(len(svgs), 1)

    def test_cli_rejects_unknown_furniture_type(self):
        code, err, svgs = self.run_layout([dict(self.BED, type="throne")])
        self.assertEqual(code, 1)
        self.assertIn("unknown furniture type 'throne' on floor 0", err)
        self.assertEqual(svgs, [])

    def test_cli_rejects_bad_facing(self):
        code, err, svgs = self.run_layout([dict(self.BED, facing="up")])
        self.assertEqual(code, 1)
        self.assertIn("facing must be N/E/S/W", err)
        self.assertEqual(svgs, [])

    def test_cli_reports_missing_size(self):
        bed = dict(self.BED)
        del bed["w"]
        code, err, svgs = self.run_layout([bed])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)


class FillTests(unittest.TestCase):
    DECK = {"name": "Deck", "fill": "#e8dcc4",
            "polygon": [[0, -2000], [6000, -2000], [6000, -100], [0, -100]]}
    POOL = {"label": "pool", "x": 1000, "y": -6000, "w": 4000, "d": 2500, "fill": "#cfe8f5"}

    def fills(self, svg):
        return re.search(r'<g id="fills">(.*?)</g>', svg, re.S).group(1).strip()

    def test_no_fill_leaves_the_group_empty(self):
        floor = box_floor(rooms=[dict(self.DECK, fill=None)], fixtures=[dict(self.POOL, fill="")])
        self.assertEqual(self.fills(DrawFloor().render({}, floor)), "")

    def test_room_fill_follows_its_polygon(self):
        group = self.fills(DrawFloor().render({}, box_floor(rooms=[self.DECK])))
        self.assertEqual(group.count("<polygon"), 1)
        self.assertIn('points="0.0,2000.0 6000.0,2000.0 6000.0,100.0 0.0,100.0"', group)
        self.assertIn('fill="#e8dcc4"', group)
        self.assertIn(f'stroke="{dp.COLORS["muted"]}"', group)
        self.assertIn(f'stroke-width="{dp.PAPER["thin"] * 50:.1f}"', group)

    def test_fixture_fill_uses_its_rectangle_and_keeps_the_dashed_outline(self):
        svg = DrawFloor().render({}, box_floor(fixtures=[self.POOL]))
        group = self.fills(svg)
        self.assertIn('points="1000.0,6000.0 5000.0,6000.0 5000.0,3500.0 1000.0,3500.0"', group)
        self.assertIn('fill="#cfe8f5"', group)
        fixtures = re.search(r'<g id="fixtures">(.*?)</g>', svg, re.S).group(1)
        self.assertIn('fill="none"', fixtures)
        self.assertIn(">pool<", fixtures)

    def test_rooms_and_fixtures_are_filled_in_order(self):
        group = self.fills(DrawFloor().render({}, box_floor(rooms=[self.DECK], fixtures=[self.POOL])))
        self.assertLess(group.index("#e8dcc4"), group.index("#cfe8f5"))

    def test_degenerate_polygon_is_skipped(self):
        room = dict(self.DECK, polygon=[[0, 0], [1000, 0]])
        self.assertEqual(self.fills(DrawFloor().render({}, box_floor(rooms=[room]))), "")

    def test_fills_are_drawn_before_everything_else_on_the_plan(self):
        floor = box_floor(rooms=[self.DECK], fixtures=[self.POOL],
                          furniture=[FurnitureInPlans.BED],
                          stairs=[{"x": 4000, "y": 500, "w": 1000, "d": 2500, "up": "N"}])
        svg = DrawFloor().render({}, floor)
        ET.fromstring(svg)
        start = svg.index('id="fills"')
        for group in ("fixtures", "furniture", "stairs", "walls", "openings", "rooms"):
            self.assertLess(start, svg.index(f'id="{group}"'), group)

    def test_filled_outdoor_area_extends_the_frame(self):
        floor = box_floor(rooms=[self.DECK])
        x0, y0, _, _ = dp.bounds(dp.floor_points(floor, dp.build_walls(floor)))
        self.assertEqual(y0, -2000)

    def test_cli_renders_fills(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "layout.json"
            p.write_text(json.dumps({"floors": [box_floor(rooms=[self.DECK], fixtures=[self.POOL])]}),
                         encoding="utf-8")
            code, out, err = run_main(p)
            self.assertEqual(code, 0, err)
            svg = (Path(tmp) / "floor-0.svg").read_text(encoding="utf-8")
            self.assertIn('fill="#e8dcc4"', svg)
            self.assertIn('fill="#cfe8f5"', svg)


class DocumentedExample(unittest.TestCase):
    """The example layout in references/floorplans.md must stay valid."""

    def test_floorplans_example_renders(self):
        md = (SKILL / "references" / "floorplans.md").read_text(encoding="utf-8")
        example = re.search(r"```json\n(.*?)```", md, re.S).group(1)
        layout = json.loads(example)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "layout.json"
            p.write_text(json.dumps(layout), encoding="utf-8")
            code, out, err = run_main(p)
            self.assertEqual(code, 0, err)
            ET.parse(Path(tmp) / "floor-0.svg")
            self.assertIn("Living", out)

    def test_floorplans_grid_example_renders(self):
        md = (SKILL / "references" / "floorplans.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)```", md, re.S)
        layout = json.loads(blocks[0])
        layout.update(json.loads(blocks[1]))
        self.assertIn("grid", layout)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "layout.json"
            p.write_text(json.dumps(layout), encoding="utf-8")
            code, out, err = run_main(p)
            self.assertEqual(code, 0, err)
            self.assertIn("columns", out)


if __name__ == "__main__":
    unittest.main()
