---
mirrors: phone_agent/windows/mcp_server.py
last_updated: 2026-04-30
status: active
---

# Feature 1-H — MCP Server (5 top-level tools)

Replaces the original "Public API + DeviceFactory" scope of 1-H. ClawGUI's
public surface is now a Model Context Protocol server over stdio. Any
MCP-compatible client (Claude Desktop, Cursor, Claude Code, ChatGPT desktop)
becomes a valid controller without us writing a controller UI.

## Definition of Done

- [ ] `mcp_server.py` boots over stdio and registers exactly 5 top-level tools.
- [ ] Each top-level tool delegates to a handler module in `mcp_handlers/`.
- [ ] All Phase 1 capability modules (1-A through 1-G) are reachable through
      one of the 5 top-level tools — no capability is exposed directly at the
      MCP boundary.
- [ ] `build_with_claw` runs a real perception-verify loop using 1-F.
- [ ] Old capability-shaped MCP tools in `server.py` are removed (they
      violated the "max 5, goal-shaped" rule).
- [ ] A Claude Desktop config snippet is in `design.md` and verified locally.
- [ ] Companion docs exist for `mcp_server.py` and every handler module.
- [ ] One end-to-end smoke test exercises each of the 5 tools.

## Status

| File | Source | Doc | Status |
|---|---|---|---|
| MCP server entry | `phone_agent/windows/mcp_server.py` | [mirror](../../phone_agent/windows/mcp_server.md) | skeleton |
| navigate handler | `phone_agent/windows/mcp_handlers/navigate.py` | [mirror](../../phone_agent/windows/mcp_handlers/navigate.md) | stub |
| build handler | `phone_agent/windows/mcp_handlers/build.py` | [mirror](../../phone_agent/windows/mcp_handlers/build.md) | stub |
| run_command handler | `phone_agent/windows/mcp_handlers/run_command.py` | [mirror](../../phone_agent/windows/mcp_handlers/run_command.md) | stub |
| inspect handler | `phone_agent/windows/mcp_handlers/inspect.py` | [mirror](../../phone_agent/windows/mcp_handlers/inspect.md) | stub |
| session handler | `phone_agent/windows/mcp_handlers/session.py` | [mirror](../../phone_agent/windows/mcp_handlers/session.md) | stub |

## Children

- [overview](overview.md) — the 5-tool contract and why these 5
- [design](design.md) — composition, transport, verify loop, client config
- [bugs](bugs.md) — bug tracker
