# ClawGUI Agent — Reusable Blocks

Shared modules usable across this project or by other projects.
See [docs/CONVENTIONS.md](docs/CONVENTIONS.md) for usage rules.

| Name | Path | Type | Description |
|------|------|------|-------------|
| Windows Screenshot | `phone_agent/windows/screenshot.py` | python-module | Captures full-screen or region screenshots on Windows via GDI/mss |
| Core GUI Actions | `phone_agent/windows/device.py` | python-module | Click, type, scroll, drag — unified Windows GUI action primitives |
| App Resolver | `phone_agent/windows/app_resolver.py` | python-module | Resolves app name → window handle / process; used by launcher and device |
| Keyboard Input | `phone_agent/windows/input.py` | python-module | Low-level keyboard event injection (SendInput / pywin32) |
| Window Manager | `phone_agent/windows/window_manager.py` | python-module | Enumerate, focus, resize, and close windows by title or PID |
| Connection Manager | `phone_agent/windows/connection.py` | python-module | Manages ADB / HDC / Tailscale connections to remote devices |
| GUI-Owl Perception Adapter | `phone_agent/perception/gui_owl_adapter.py` | python-module | Wraps GUI-Owl model to return element bounding boxes from screenshots |
| Step Memory | `phone_agent/memory/step_memory.py` | python-module | Persists per-task step history; reusable for any multi-step agent loop |
| Test Safety Layer | `phone_agent/windows/safety.py` | python-module | Guards against dangerous GUI actions during automated tests |
| App Registry | `phone_agent/windows/app_registry.py` | python-module | PID-scoped, cross-run registry of opened apps; usable by any agent |
| MCP Server (5 tools) | `phone_agent/windows/mcp_server.py` | mcp-server | Exposes ClawGUI actions as MCP tools for Claude Code / any MCP client |
| Gradio Web UI | `webui.py` | python-module | Full Gradio control panel — device mgmt, task input, live screenshots |
