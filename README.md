# 3d-builder

An agent skill that makes your AI agent build and edit 3D models in Blender or FreeCAD in a spec-driven way.

If you ask an agent for a 3D model straight away, it guesses at dimensions, proportions and details, and you end up correcting it over and over. With this skill, the agent first writes down what it is going to build in a spec file. It asks you about anything that is unclear, and only then starts modelling. Each spec stays in your project as a record of what was asked for and decided.

## Requirements

- **An agent that supports skills**, such as Claude Code.
- **A capable model.** Opus or an equivalent model is strongly recommended. Smaller models produce noticeably worse models.
- **Blender or FreeCAD**, installed locally.
- **Optional: a Blender or FreeCAD MCP server**, configured in your agent. Without one, the skill falls back to generating Python scripts (see [Modelling](#3-modelling)).

## Install

```shell
npx skills add thanikc/3d-builder
```

## Usage

You don't need to call the skill explicitly. It triggers when your agent sees from the conversation that a 3D model should be created or edited. For example:

> Build a wall-mounted holder for a 60 mm wide phone with a cable slot at the bottom.

When it's done, your project contains:

```
specs/
  2026-11-18-143005-phone-holder.md   # what was asked, decided and assumed
models/
  phone-holder.blend                  # or .FCStd for FreeCAD
```

## How it works

### 1. Writing the spec

1. The agent creates the `specs/` folder if it doesn't exist yet.
2. It writes a new spec file for your request, named `<yyyy-mm-dd-hhmmss>-<name>.md`.

### 2. Clarifying questions

If your request is ambiguous, the agent asks questions one at a time:

- Where possible, each question can be answered with yes or no.
- Otherwise it offers multiple choice, with the recommended option first and a free-text answer last.
- After 5 questions, it asks whether it should continue with up to 5 more, and so on.

The questions stop when nothing is left unclear or when you choose to stop answering. For any open points that remain, the agent decides how to handle them and writes that decision in the spec, so you can see every assumption it made.

### 3. Modelling

The agent then creates or edits the model and saves it to the `models/` folder.

1. **MCP first.** It uses a Blender or FreeCAD MCP server if one is configured.
2. **Choosing a tool.** If both are configured, or neither is, it asks which tool you want to use and remembers your choice.
3. **Script fallback.** If no MCP server is available, or the server doesn't respond within 10 seconds, it generates a Python script for Blender or FreeCAD that builds the model.
