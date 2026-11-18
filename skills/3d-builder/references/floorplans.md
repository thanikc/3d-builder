# Floor plans for buildings

Read this when the model is a building or has rooms: a house, cabin, apartment, office, shop, barn, garage, tower, a game level building with an interior, a dollhouse. The plans let the user see and correct the layout on paper before any 3D geometry exists. Moving a wall on a plan is cheap. Moving it in a finished model is a rebuild.

**Exterior-only buildings** (a background prop or a facade with no interior): ask one yes/no question, "Should I draw a footprint plan first?". A footprint with door and window positions still helps. If the user says no, skip this phase and record that under **Decisions**.

## 1. Discuss the floor plan

This uses the same rules as the clarifying questions: one question at a time, yes/no or multiple choice, batches of 5, and each answer recorded in **Decisions**. Ask in roughly this order and skip anything the user has already said:

1. Number of floors (and a basement or attic?), floor-to-floor height
2. Footprint: overall size or plot limits, shape (rectangle, L, U), which side faces the street or north
3. Room programme per floor: which rooms there are and their rough size (m² or "small/medium/large")
4. Adjacency: what must be next to what (kitchen beside dining, bathroom near the bedrooms, entrance into a hall)
5. Entrance(s) and stairs: position, straight or L-shaped stairs
6. Wall thickness (exterior/interior), doors and windows (sizes, sill heights, which rooms need daylight)
7. Roof type and overhang. The roof doesn't go in the plans, but it affects the top floor.

Don't ask for coordinates. Propose a layout instead, because a user can react to a drawing far more easily than to an abstract question. If the programme is clear after 2–3 questions, draw a first version and refine it from there.

## 2. Draw the plans

Plans live in the model's folder, next to its specs:

```
models/<name>/plans/
  layout.json      # the source of truth: walls, openings, rooms, stairs per floor
  floor-0.svg      # generated: one SVG per floor
  floor-1.svg
```

Write `layout.json` (format below), then generate the SVGs with the bundled script:

```bash
python3 <skill-dir>/scripts/draw_plans.py models/<name>/plans/layout.json
```

The script needs Python 3 only. It checks the layout (unknown walls, openings that don't fit or overlap), writes one SVG per floor at a fixed drawing scale, and prints the room areas. All floors share one frame, so stacked sheets line up. Fix any reported error and rerun. Never hand-edit the SVGs: change `layout.json` and regenerate.

**Check the drawing yourself before showing it.** If you can view images, rasterize the SVG and look at it (`rsvg-convert -o floor-0.png floor-0.svg`, `inkscape floor-0.svg -o floor-0.png`, or a headless Chrome/Edge `--screenshot`). Check that rooms are closed, doors swing into sensible spaces, stairs line up between floors and labels don't collide.

## 3. Review with the user

Show the plans: give the SVG paths (they open in any browser or IDE), and if your environment can display images or publish pages, show them inline as well. Summarise each floor in a few lines: rooms with areas, the total area and anything you decided on your own.

Then ask: "Does this layout work, or what should change?". Apply the changes to `layout.json`, regenerate and show the result again. Repeat until the user approves. Record the approval and any changes in **Decisions**, and record layout choices you made yourself in **Assumptions**. **Don't start modelling until the user has approved the plans** (or told you to go ahead without reviewing them).

## Layout format

All coordinates are in mm, with x pointing east (right on the sheet) and y pointing north (up on the sheet). Put the origin at a building corner.

```json
{
  "name": "Lake cabin",
  "units": "mm",
  "scale": 50,
  "north": 0,
  "floors": [
    {
      "id": "0",
      "name": "Ground floor",
      "elevation": 0,
      "height": 2900,
      "walls": [
        {"id": "s", "from": [9000, 0], "to": [0, 0], "thickness": 300, "type": "exterior"},
        {"id": "w", "from": [0, 0], "to": [0, 7000], "thickness": 300, "type": "exterior"},
        {"id": "i1", "from": [5000, 0], "to": [5000, 7000], "thickness": 120}
      ],
      "openings": [
        {"wall": "s", "type": "door", "offset": 1500, "width": 1000, "height": 2100, "hinge": "start", "swing": "right"},
        {"wall": "w", "type": "window", "offset": 2000, "width": 2400, "sill": 600, "head": 2200},
        {"wall": "i1", "type": "opening", "offset": 800, "width": 1200, "height": 2100}
      ],
      "rooms": [
        {"name": "Living", "polygon": [[150, 150], [4940, 150], [4940, 6850], [150, 6850]]}
      ],
      "stairs": [{"x": 7800, "y": 300, "w": 1000, "d": 3000, "up": "N", "steps": 14, "label": "UP"}],
      "fixtures": [{"label": "kitchen counter", "x": 5100, "y": 6200, "w": 3000, "d": 600}]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `scale` | Drawing scale 1:`scale` (default 50; use 100 for large buildings) |
| `north` | Optional. Angle of north in degrees, clockwise from up on the sheet; draws a north arrow |
| floor `id` | Used in the file name: `"0"` ground, `"1"` first floor, `"b1"` basement → `floor-b1.svg` |
| floor `elevation`, `height` | Floor level and floor-to-floor height in mm (used by the model) |
| wall `from`, `to` | Wall **centreline** endpoints. Walls that meet at a corner must share an endpoint exactly; a wall ending on another wall's centreline makes a T-junction |
| wall `thickness`, `type` | Total thickness in mm (default 200); `"exterior"` or `"interior"` (default). Overall dimensions are measured over the exterior walls |
| opening `offset`, `width` | Distance along the wall from its `from` point to the opening's near edge, and the opening width |
| opening `type` | `"door"`, `"window"` or `"opening"` (a doorless passage) |
| door `hinge`, `swing` | `hinge`: `"start"` or `"end"` jamb (start = the side nearer `from`). `swing`: `"left"` or `"right"` of the wall, looking from `from` to `to` |
| door/opening `height`; window `sill`, `head` | Heights above floor level in mm, for the model (defaults: door 2100, sill 900, head 2100) |
| room `polygon` | Room outline along the **inner wall faces** (so areas are net floor areas); optional `label_at` |
| stairs | Rectangle `x, y` (south-west corner), `w` (east–west), `d` (north–south); `up` is the climbing direction `N/S/E/W`; draw the stairs on every floor they connect, labelled `UP` below and `DN` above |
| fixtures | Optional dashed rectangles for furniture or fittings that affect the layout |

Keep wall ids stable between revisions so edits stay readable.

## 4. Build the model from the layout

The model must match the approved plans exactly, so build it **from `layout.json`**: the build code (MCP calls or `<name>.py`) reads the file and doesn't retype the coordinates. Then a change to the plan flows into the model by rebuilding it.

- **Walls:** for each wall, a box along the centreline with the wall's thickness, from `elevation` to `elevation + height` (subtract the slab thickness if the spec has slabs). Where wall endpoints meet another wall's endpoint, extend the wall past its endpoint by half the other wall's thickness, as the plan script does, so corners close without gaps or overlaps.
- **Openings:** subtract a box for each one: doors and passages from floor level to `height`, windows from `sill` to `head`, and slightly deeper than the wall so the boolean cuts cleanly. Add frames, glass or door leaves only if the spec asks for that level of detail.
- **Slabs:** one per floor, covering the outer faces of the exterior walls, with a hole where stairs pass through.
- **Stairs:** step count and footprint from the layout, rise = floor-to-floor height / steps.
- **Roof:** from the spec, since it's not part of the plans.

In Blender, give each floor its own collection (`Floor 0`, `Floor 1`, …) so the user can hide upper floors and look inside. In FreeCAD, use one group per floor. Check the result against the layout: the outer bounding box matches the plan's overall dimensions, every opening is present, and the floor levels are correct.

## Editing a building

Change the plans first. Update `layout.json` and regenerate the SVGs. Show the user what changes, ideally by comparing the old and new sheets. If the old SVGs aren't in version control, keep copies as `floor-<id>.prev.svg` while reviewing. Only change the model after the user approves the new plan. Record the change in the new spec, listing which walls and openings were added, moved or removed.
