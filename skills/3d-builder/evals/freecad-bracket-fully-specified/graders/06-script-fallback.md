---
type: llm
focus: trace
weight: 1
---

Without a FreeCAD MCP server, the agent wrote models/<name>/<name>.py that imports FreeCAD and Part (not FreeCADGui), defines the key dimensions as named constants at the top, and saves <name>.FCStd next to the script.
