# Spec template

Copy this into `models/<name>/specs/<yyyy-mm-dd-hhmmss>-<request>.md`. Paths inside the spec are relative to `models/<name>/`. Drop sections that are empty and wouldn't help anyone (e.g. **Previous spec** for a new model), but always keep **Decisions** and **Assumptions**, even if one just says "None".

```markdown
# <Object name>

- **Created:** <yyyy-mm-dd hh:mm:ss>
- **Status:** draft | clarifying | planning | modelling | done
- **Tool:** Blender | FreeCAD (via MCP | via script)
- **Previous spec:** specs/<file>.md  <!-- edits only -->

## Request

> <the user's request, verbatim>

## Summary

<2–4 sentences: what the object is, what it's for, how it will be made or used (3D print, CNC, render-only, game/web asset for <engine>).>

## Requirements

All dimensions in mm unless stated otherwise (for game/web assets, state the engine units, e.g. 1 unit = 1 m).

| Feature | Value | Source |
|---|---|---|
| Overall width | 68 mm | decision |
| Phone slot width | 62 mm (60 mm phone + 1 mm clearance per side) | request + assumption |
| ... | ... | request / decision / assumption |

<For game/web assets, also rows for: target engine, triangle budget, scale/units, pivot, UVs/textures, LODs, collision mesh.>

<For buildings, also rows for: number of floors, floor-to-floor height, footprint, wall thicknesses, roof. Add a "Floors" list with one line per floor naming its rooms and their areas. The exact layout lives in plans/layout.json, so don't copy coordinates into the spec.>

<For edits: a "Changes" list and a "Must stay the same" list instead of, or in addition to, the table.>

## Decisions

Answers from the user, in the order asked.

1. **<question>** → <answer>

## Assumptions

Open points the agent decided on its own, each with a reason.

- <assumption>: <why this is a sensible default>

## Output

- Model: `<name>.blend` / `<name>.FCStd`
- Script: `<name>.py`  <!-- script fallback only -->
- Export: `<name>.glb` / `<name>.fbx`  <!-- game/web assets only -->
- Plans: `plans/layout.json`, `plans/floor-<id>.svg` (approved <date>)  <!-- buildings only -->
- Verified: <bounding box, features checked; triangle count for game/web assets>
- Notes: <anything that turned out different from the plan>

## Revisions

<small follow-up changes made in the same session, newest last>
```
