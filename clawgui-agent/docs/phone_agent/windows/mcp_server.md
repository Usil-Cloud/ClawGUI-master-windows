---
mirrors: phone_agent/windows/mcp_server.py
last_updated: 2026-04-30
status: active
---

# mcp_server

## Purpose

FastMCP entry point for ClawGUI's public surface. Registers exactly five
top-level tools and runs them over stdio. Each decorator is a thin wrapper
that delegates to a handler module — keeping this file the canonical answer
to "what tools does ClawGUI expose?".

## Approach

- Built on `mcp.server.fastmcp.FastMCP` (the same library 1-E `server.py` uses).
- stdio transport only. Remote use is via SSH-tunneled stdio over Tailscale.
- Five `@mcp.tool()` decorators, all goal-shaped. No capability-shaped tools.
- Real logic lives in `phone_agent/windows/mcp_handlers/`. Each tool wrapper is one delegation call.
- `python -m phone_agent.windows.mcp_server` is the run command.

## Status

Skeleton — tool wrappers exist and stdio boots, but handlers return stub data.
Implementation order: `inspect_screen` → `navigate_windows` → `run_command`
→ `manage_session` → `build_with_claw`.

## Known Bugs

None yet.

## Linked Docs

- Parent: `docs/features/mcp_server/_index.md`
- Design: `docs/features/mcp_server/design.md`
- Handlers: `docs/phone_agent/windows/mcp_handlers/_index.md`
