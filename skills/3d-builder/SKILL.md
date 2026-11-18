---
name: 3d-builder
description: Spec-driven creation and editing of 3D models in Blender or FreeCAD. Writes a spec file in specs/, asks clarifying questions one at a time, records every decision and assumption, then builds the model via a Blender/FreeCAD MCP server or a generated Python script and saves it to models/. Use whenever the user wants a 3D model, part, object, enclosure, bracket, holder, mount, case, prop, mesh or CAD design created or changed - even if they don't mention Blender, FreeCAD or "3D" explicitly (e.g. "design a wall mount for my router", "make the hook 5 mm thicker", "I need a printable box for an Arduino"). Not for questions about 3D concepts, rendering-only tasks on an existing scene, or game/web 3D code (three.js, Unity).
---

# 3d-builder

Don't guess at a 3D model. Write down what will be built, clear up what's ambiguous with the user, record every assumption, and only then model it. A model built on guessed dimensions gets corrected over and over; a spec catches the guesses before they become geometry.

The workflow has three phases, always in this order: **spec → questions → model**. Don't open Blender or FreeCAD, and don't write modelling code, before the spec exists and the questions are done.

## Phase 1: Write the spec

1. Create `specs/` in the project root if it doesn't exist.
2. Get the timestamp from the system clock (e.g. `date +%Y-%m-%d-%H%M%S`) rather than inventing one.
3. Pick a short kebab-case name for the object (`phone-holder`, `router-wall-mount`). Reuse the same name for the model file later.
4. Create `specs/<yyyy-mm-dd-hhmmss>-<name>.md` using the template in [references/spec-template.md](references/spec-template.md).

Fill in what the request already states, then list the open points: everything that affects the geometry but wasn't specified. Typical open points:

- Overall dimensions and units, and which dimensions are fixed vs. free
- Fit and clearance against real objects (a 60 mm phone needs a slot slightly wider than 60 mm; how much?)
- Wall thickness, fillets/chamfers, hole sizes, screw types
- Mounting method, orientation, load
- Purpose and manufacturing (3D printing → overhangs, minimum walls, flat base; CNC; render-only)
- Level of detail, materials (Blender), parametric needs (FreeCAD)

**Editing an existing model:** look in `specs/` and `models/` for the object first. Write a new spec for the change (each request gets its own file, so the history stays readable), link it to the previous spec, and state what changes and what must stay the same. Read the existing model (via MCP, or the script that built it) before editing, so the edit starts from what's actually there.

## Phase 2: Clarifying questions

If the request leaves open points, ask about them before modelling. The user knows things you can't infer (the actual phone width, where the wall screws go), and one question now saves a rebuild later.

Rules:

- **One question at a time.** Wait for the answer before asking the next. Order questions by how much they affect the geometry: overall size and purpose first, cosmetic details last.
- **Yes/no where possible.** "Should the cable slot be centred?" beats "Where should the cable slot be?".
- **Otherwise multiple choice:** the recommended option first and marked "(recommended)", then the alternatives, and a free-text answer last. Use the agent's question tool (e.g. AskUserQuestion) if it has one; it usually adds the free-text option for you.
- **Batches of 5.** After every 5 questions, ask whether to continue with up to 5 more, saying roughly how many open points are left. If the user says no, stop asking.
- Don't ask about things that don't matter to this model, and don't ask what the user already said.
- Record each answer in the spec's **Decisions** section right away, so the spec is always current.

Stop when nothing important is left unclear, or when the user stops answering. For every open point that remains, decide yourself, choosing the sensible default for the stated purpose, and write it in **Assumptions** with a one-line reason. The user should be able to read the spec and see every choice made on their behalf.

If the request is already fully specified, skip the questions and say so in one line.

## Phase 3: Model

Save the result to `models/<name>.blend` (Blender) or `models/<name>.FCStd` (FreeCAD). Create `models/` if needed.

### Choose the tool

Check which MCP servers are configured: look at your available tools for Blender or FreeCAD MCP tools (names usually contain `blender` or `freecad`).

1. **Remembered choice:** if `.3d-builder.json` exists in the project root, use its `"tool"` (`"blender"` or `"freecad"`) unless the user asks for something else.
2. **Exactly one MCP server configured:** use that tool.
3. **Both or neither configured:** ask the user which tool to use (one multiple-choice question). Recommend FreeCAD for functional parts with precise dimensions (brackets, enclosures, anything printed or machined), and Blender for organic shapes, sculpted or decorative objects, and anything meant for rendering.
4. Remember the choice by writing `{"tool": "blender"}` or `{"tool": "freecad"}` to `.3d-builder.json`. Record the tool in the spec too.

### Build via MCP (preferred)

1. Make one cheap call first (e.g. get scene/document info). If it errors or doesn't respond within **10 seconds**, treat the server as unavailable and switch to the script fallback. Tell the user why in one line.
2. Build the model step by step from the spec. Check dimensions as you go (query bounding boxes or object properties) rather than trusting that the code did what you meant.
3. Save to the path above.

### Script fallback

When no MCP server is usable, write a standalone Python script, `models/<name>.py`, that builds the model from scratch and saves it to `models/<name>.blend` or `models/<name>.FCStd`. Put the key dimensions as named constants at the top so the user can tweak them.

Then try to run it headless, if the tool is installed:

- Blender: `blender --background --python models/<name>.py`
- FreeCAD: `freecadcmd models/<name>.py` (on some systems `FreeCADCmd` or `freecad.cmd`)

If it runs, check the output (file exists, printed bounding box matches the spec). If it fails, fix the script and rerun. If the tool isn't on the PATH, tell the user the exact command to run.

Tool-specific pitfalls and script skeletons: [references/blender.md](references/blender.md), [references/freecad.md](references/freecad.md). Read the one for the chosen tool before writing code.

### Finish

1. Verify the model against the spec: overall dimensions, every listed feature present, and any fit or clearance requirements.
2. Update the spec: set **Status** to `done`, fill in **Output** (file paths, tool, MCP or script), and note anything that turned out different from the plan.
3. Report to the user briefly: what was built, where the files are, and the main assumptions they may want to revisit (point to the spec for the rest).

If the user asks for changes after that, treat them as a new edit request (Phase 1, "Editing an existing model"). Small follow-ups in the same conversation ("a bit thicker") can go in the same spec under **Revisions** instead.
