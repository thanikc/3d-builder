# Blender notes

## Pitfalls

- **Units.** Blender's default unit is the metre: 1 Blender unit = 1 m. For mm-scale parts, either set `scene.unit_settings.scale_length = 0.001` and `length_unit = 'MILLIMETERS'` and model in mm, or keep metres and convert (`mm = 0.001`). Choose one and say which in the spec. Mixing them is the most common way a 60 mm holder comes out 60 m wide.
- **Primitive sizes.** `primitive_cube_add(size=2)` gives a 2×2×2 cube centred on the origin. Use `size=1` and then `scale = (w, d, h)` to get exact dimensions, and apply the scale (`bpy.ops.object.transform_apply(scale=True)`) before booleans or exporting.
- **Booleans.** Use the `BOOLEAN` modifier with `solver='EXACT'`. Make cutters slightly longer than the wall they cut through (+0.1 mm each side), because coplanar faces cause broken booleans. Apply the modifier, then delete or hide the cutter.
- **Printable meshes.** For 3D printing, keep the mesh manifold: no zero-thickness faces, normals pointing outward (`bpy.ops.mesh.normals_make_consistent`). Bevels via the `BEVEL` modifier.
- **Context.** `bpy.ops` calls depend on the active object and mode. In scripts, prefer `bpy.data` and `bmesh` where practical, or set `view_layer.objects.active` explicitly.
- **Measure.** Check the result with each object's `dimensions` (after applying modifiers) or a bounding box from `evaluated_get(depsgraph)`.

## Script skeleton (fallback)

```python
# Build <name>. Run: blender --background --python models/<name>.py
import bpy, os

# --- Parameters (mm) ---
WIDTH = 68.0
DEPTH = 20.0
HEIGHT = 90.0
WALL = 3.0

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "<name>.blend")

# Clean scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.unit_settings.scale_length = 0.001  # 1 Blender unit = 1 mm

def box(name, w, d, h, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    return ob

def cut(target, cutter):
    mod = target.modifiers.new("cut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

body = box("body", WIDTH, DEPTH, HEIGHT, (0, 0, HEIGHT / 2))
# ... build features ...

print("dimensions (mm):", tuple(round(v, 2) for v in body.dimensions))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
```
