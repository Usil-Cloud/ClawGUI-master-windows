---
last_updated: 2026-04-30
status: active
---

# mcp_handlers

Handler modules for the five MCP top-level tools. Each module owns the full
implementation of one tool, including any helper functions and the result
dataclass. The `mcp_server.py` decorators are thin wrappers that delegate
here.

- [navigate](navigate.md) — `navigate_windows` · GUI navigation, no verify · status: stub
- [build](build.md) — `build_with_claw` · GUI navigation with verify loop · status: stub
- [run_command](run_command.md) — `run_command` · CLI execution mode · status: stub
- [inspect](inspect.md) — `inspect_screen` · read-only screen probe · status: stub
- [session](session.md) — `manage_session` · co-working session control · status: stub
