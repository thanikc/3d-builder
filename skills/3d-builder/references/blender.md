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
# Build <name>. Run: blender --background --python models/<name>/<name>.py
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

## Game and web assets

- **Units: model in metres.** Engines treat 1 unit as 1 m (Unreal uses cm, but its FBX importer converts from metres). The glTF exporter ignores `scale_length`, so a part modelled with the mm setup above exports 1000× too large. For engine assets keep `scale_length = 1.0` and model in metres.
- **Axes.** Blender is Z-up; glTF and most engines are Y-up. The glTF exporter converts by default (`export_yup=True`). For FBX, use `axis_forward='-Z', axis_up='Y'`. Model the asset facing −Y in Blender, which becomes +Z forward in glTF.
- **Pivot.** The object origin becomes the pivot in the engine. Put it where the spec says (usually bottom centre for props so they sit on the floor, or the hinge point for doors) and leave the object at the world origin with rotation 0 and scale 1, so all transforms are applied.
- **Triangle budget.** Count triangles on the evaluated mesh (sum of `len(poly.vertices) - 2` over the polygons) and compare with the budget in the spec. Avoid bevels and subdivision you can't afford; use the `DECIMATE` modifier for LODs.
- **Normals and shading.** Set smooth or flat shading on purpose, and use auto smooth / `WEIGHTED_NORMAL` for hard-edged props. Keep normals pointing outward, because engines cull back faces.
- **Materials.** Only Principled BSDF inputs (base colour, metallic, roughness, normal map, emission, alpha) survive export. Procedural node setups don't, so bake them to image textures. UV-unwrap every mesh that uses a texture, and use one material per asset where possible (fewer draw calls).
- **LODs and collision.** Follow the engine's import naming: Unity and Unreal recognise `<name>_LOD0`, `<name>_LOD1`, … in FBX; Unreal uses `UCX_<name>` for convex collision meshes; Godot uses a `-col` (trimesh) or `-colonly` suffix. Godot generates LODs on import, so only make them by hand for Unity or Unreal when the spec asks.
- **Export only the asset.** Delete or exclude cutters, helper objects, cameras and lights before exporting (`use_selection=True` with only the asset selected).

Export snippet, appended to the script (or run via MCP) after the asset is built:

```python
# Make sure only the asset (plus LOD/collision meshes) is selected
bpy.ops.object.select_all(action='DESELECT')
asset.select_set(True)
bpy.context.view_layer.objects.active = asset

base = os.path.splitext(OUT)[0]

# glTF binary: web, Godot, general use
bpy.ops.export_scene.gltf(
    filepath=base + ".glb", export_format='GLB',
    use_selection=True, export_apply=True, export_yup=True,
)

# FBX: Unity, Unreal
bpy.ops.export_scene.fbx(
    filepath=base + ".fbx", use_selection=True,
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
    mesh_smooth_type='FACE',
)

deps = bpy.context.evaluated_depsgraph_get()
mesh = asset.evaluated_get(deps).to_mesh()
tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
print("triangles:", tris, "dimensions (m):", tuple(round(v, 3) for v in asset.dimensions))
```
