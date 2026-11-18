# Build wall-hook. Run: freecadcmd models/wall-hook/wall-hook.py
import os
import FreeCAD as App
import Part

# --- Parameters (mm) ---
PLATE_W = 30.0
PLATE_H = 80.0
PLATE_T = 5.0
HOOK_LEN = 45.0
HOOK_T = 6.0
TIP_H = 15.0
HOLE_D = 4.5
HOLE_INSET = 15.0

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wall-hook.FCStd")
V = App.Vector

doc = App.newDocument("wall-hook")

plate = Part.makeBox(PLATE_W, PLATE_T, PLATE_H)
arm = Part.makeBox(PLATE_W, HOOK_LEN, HOOK_T, V(0, PLATE_T, 0))
tip = Part.makeBox(PLATE_W, HOOK_T, TIP_H, V(0, PLATE_T + HOOK_LEN - HOOK_T, HOOK_T))
body = plate.fuse(arm).fuse(tip)

for z in (HOLE_INSET, PLATE_H - HOLE_INSET):
    hole = Part.makeCylinder(HOLE_D / 2, PLATE_T + 0.2, V(PLATE_W / 2, -0.1, z), V(0, 1, 0))
    body = body.cut(hole)

assert body.isValid(), "invalid shape"
obj = doc.addObject("Part::Feature", "wall-hook")
obj.Shape = body
doc.recompute()

bb = body.BoundBox
print("bbox (mm):", round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2))
doc.saveAs(OUT)
print("saved", OUT)
