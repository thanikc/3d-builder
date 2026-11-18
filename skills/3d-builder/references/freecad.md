# FreeCAD notes

## Pitfalls

- **Units.** FreeCAD works in mm internally. Plain numbers in `Part` calls are mm.
- **Part vs. PartDesign.** For scripts, `Part` (CSG on shapes: `makeBox`, `makeCylinder`, `cut`, `fuse`, `fillet`) is the most predictable choice. PartDesign (sketch → pad/pocket) gives a nicer parametric tree in the GUI, but it is fragile to script because of sketch constraints and topological naming. Use it only if the user wants an editable feature history.
- **Placement.** `Part.makeBox(l, w, h)` starts at the origin corner, not the centre. `makeCylinder(r, h, base, dir)` takes a base point and a direction vector. Work out the coordinates on purpose rather than by trial and error.
- **Booleans.** Make cutters extend past the faces they cut (+0.1 mm), to avoid coplanar faces. Check `shape.isValid()` after booleans and fillets.
- **Fillets.** `shape.makeFillet(r, edges)` fails if the radius is too large for an adjacent face. Select edges by position (e.g. filter `shape.Edges` by `BoundBox`) instead of hard-coded edge indices, which change whenever the geometry changes.
- **Headless.** In `freecadcmd` there is no GUI: don't import `FreeCADGui` and don't touch `ViewObject`.
- **Measure.** `shape.BoundBox` gives `XLength`, `YLength` and `ZLength`. Print them to verify the result.

## Script skeleton (fallback)

```python
# Build <name>. Run: freecadcmd models/<name>.py
import os
import FreeCAD as App
import Part

# --- Parameters (mm) ---
WIDTH = 68.0
DEPTH = 20.0
HEIGHT = 90.0
WALL = 3.0

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "<name>.FCStd")
V = App.Vector

doc = App.newDocument("<name>")

body = Part.makeBox(WIDTH, DEPTH, HEIGHT)
# cutter = Part.makeBox(..., ..., ..., V(x, y, z))
# body = body.cut(cutter)
# ... build features ...

assert body.isValid(), "invalid shape"
obj = doc.addObject("Part::Feature", "<name>")
obj.Shape = body
doc.recompute()

bb = body.BoundBox
print("bbox (mm):", round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2))
doc.saveAs(OUT)
print("saved", OUT)
```

If `__file__` isn't defined (some FreeCAD versions run scripts through `exec`), fall back to `os.getcwd()` and run the script from the project root.
