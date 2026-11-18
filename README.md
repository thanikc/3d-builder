# 3d-builder

An agent skill that makes your AI agent build and edit 3D models in Blender or FreeCAD in a spec-driven way. That includes printable parts and CAD designs as well as assets for games and the web (exported as `.glb` or `.fbx` for three.js, Unity, Unreal or Godot).

If you ask an agent for a 3D model straight away, it guesses at dimensions, proportions and details, and you end up correcting it over and over. With this skill, the agent first writes down what it is going to build in a spec file. It asks you about anything that is unclear, and only then starts modelling. Each spec stays in your project as a record of what was asked for and decided.

## Requirements

- **An agent that supports skills**, such as Claude Code.
- **A capable model.** Opus or an equivalent model is strongly recommended. Smaller models produce noticeably worse models.
- **Blender or FreeCAD**, installed locally.
- **Optional: a Blender or FreeCAD MCP server**, configured in your agent. Without one, the skill falls back to generating Python scripts (see [Modelling](#4-modelling)).

## Install

```shell
npx skills add thanikc/3d-builder
```

## Usage

You don't need to call the skill explicitly. It triggers when your agent sees from the conversation that a 3D model should be created or edited. For example:

> Build a wall-mounted holder for a 60 mm wide phone with a cable slot at the bottom.

> Make a low-poly wooden crate for my Godot game.

> Model a two-storey cabin with an open kitchen and two bedrooms upstairs.

When it's done, each model has its own folder under `models/` with everything that belongs to it, so a project can hold any number of models:

```
models/
  phone-holder/
    specs/
      2026-11-18-143005-initial.md        # what was asked, decided and assumed
      2026-11-19-091200-thicker-hook.md   # one spec per later change
    phone-holder.blend                    # or .FCStd for FreeCAD
  cabin/
    specs/
      2026-11-18-150210-initial.md
    plans/                                # buildings only: the approved floor plans
      layout.json                         # walls, doors, windows, rooms, stairs per floor
      floor-0.svg                         # one vector plan per floor
      floor-1.svg
    cabin.blend
```

## How it works

### 1. Writing the spec

1. The agent creates the model's folder, `models/<name>/`, with a `specs/` folder inside it.
2. It writes a new spec file for your request, named `<yyyy-mm-dd-hhmmss>-<request>.md` (`initial` for a new model, a short label like `thicker-hook` for a change).

### 2. Clarifying questions

If your request is ambiguous, the agent asks questions one at a time:

- Where possible, each question can be answered with yes or no.
- Otherwise it offers multiple choice, with the recommended option first and a free-text answer last.
- After 5 questions, it asks whether it should continue with up to 5 more, and so on.

The questions stop when nothing is left unclear or when you choose to stop answering. For any open points that remain, the agent decides how to handle them and writes that decision in the spec, so you can see every assumption it made.

### 3. Floor plans (buildings only)

If the model is a building, the agent works out the layout with you before it builds anything:

1. It asks about floors, footprint, rooms, stairs, doors and windows, following the same one-question-at-a-time rules.
2. It writes the layout to `models/<name>/plans/layout.json` and turns it into an SVG plan for each floor with the bundled `draw_plans.py` script, which needs Python 3 only. Each plan shows the walls, door swings, windows, stairs, room names with areas, overall dimensions and a scale bar.
3. It shows you the plans and revises them until you approve. Then it builds the 3D model from the same `layout.json`, so the model matches the plans exactly.

When you later change a building, the plans are updated and approved first, and only then is the model changed.

### 4. Modelling

The agent then creates or edits the model and saves it in the model's folder.

1. **MCP first.** It uses a Blender or FreeCAD MCP server if one is configured.
2. **Choosing a tool.** If both are configured, or neither is, it asks which tool you want to use and remembers your choice.
3. **Script fallback.** If no MCP server is available, or the server doesn't respond within 10 seconds, it generates a Python script for Blender or FreeCAD that builds the model.

### Game and web assets

For assets meant for a game engine or a web page, the agent also asks about engine-specific points like the target engine, polygon budget, scale, pivot, textures, LODs and collision. It builds the asset in Blender and exports it next to the `.blend` file: `.glb` for the web and Godot, `.fbx` for Unity and Unreal. It checks the triangle count against the budget.

The skill delivers the asset file only. It doesn't write engine scripts or scene code.
