# Spec template

Copy this into `specs/<yyyy-mm-dd-hhmmss>-<name>.md`. Drop sections that are empty and wouldn't help anyone (e.g. **Previous spec** for a new model), but always keep **Decisions** and **Assumptions**, even if one just says "None".

```markdown
# <Object name>

- **Created:** <yyyy-mm-dd hh:mm:ss>
- **Status:** draft | clarifying | modelling | done
- **Tool:** Blender | FreeCAD (via MCP | via script)
- **Previous spec:** specs/<file>.md  <!-- edits only -->

## Request

> <the user's request, verbatim>

## Summary

<2–4 sentences: what the object is, what it's for, how it will be made (3D print, CNC, render-only).>

## Requirements

All dimensions in mm unless stated otherwise.

| Feature | Value | Source |
|---|---|---|
| Overall width | 68 mm | decision |
| Phone slot width | 62 mm (60 mm phone + 1 mm clearance per side) | request + assumption |
| ... | ... | request / decision / assumption |

<For edits: a "Changes" list and a "Must stay the same" list instead of, or in addition to, the table.>

## Decisions

Answers from the user, in the order asked.

1. **<question>** → <answer>

## Assumptions

Open points the agent decided on its own, each with a reason.

- <assumption>: <why this is a sensible default>

## Output

- Model: `models/<name>.blend` / `models/<name>.FCStd`
- Script: `models/<name>.py`  <!-- script fallback only -->
- Verified: <bounding box, features checked>
- Notes: <anything that turned out different from the plan>

## Revisions

<small follow-up changes made in the same session, newest last>
```
