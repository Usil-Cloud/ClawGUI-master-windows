---
mirrors: phone_agent/windows/mcp_server.py
last_updated: 2026-04-30
status: active
---

# MCP Server — Overview

## Why an MCP server

Original Phase 1-H scope was "Public API + DeviceFactory + a controller". MCP
collapses the controller question entirely — Claude Desktop, Cursor, Claude
Code, and ChatGPT desktop are already MCP clients. Wrapping ClawGUI as an MCP
server means the controller is whatever the user already has open. We stop
building UI and start shipping intent.

## The 5-tool contract

Top-level tools are **goal-shaped**, not capability-shaped. A capability surface
("click", "screenshot", "type") would let an LLM compose primitives in any
shape — including wrong ones — which makes the MCP slow, expensive, and
unreliable. A goal surface forces the client to declare intent. Each goal tool
internally composes whatever capabilities it needs.

The cap is **five**.

| # | Tool | Intent | Verifies completion? | Mode |
|---|---|---|---|---|
| 1 | `navigate_windows` | Reach a UI state on the target machine. Open/focus app, click/type/scroll until a position is reached. Returns final screenshot + state. | No — best-effort | GUI |
| 2 | `build_with_claw` | Execute a goal end-to-end with a verification loop: plan → act → re-perceive → judge done? → retry. Returns transcript + final artifact + pass/fail. | **Yes** — server-side LLM verify | GUI |
| 3 | `run_command` | Execute a shell command on the target. Returns stdout, stderr, exit code, optional file captures. | Exit code only | CLI |
| 4 | `inspect_screen` | Read-only probe. Returns screenshot + GUI-Owl structured screen parse. The cheap "what's there?" before deciding to act. | n/a | GUI (read-only) |
| 5 | `manage_session` | Co-working session control. List active apps, save/restore step memory (1-G), close app, reset, kill switch. | n/a | meta |

## Why exactly these 5

- 1 + 2 are the user's two anchors — GUI mode with and without verification.
- 3 is the *other execution mode* in the product vision (the "show me Downloads → `dir`" case). It cannot fold into 1 or 2 without lying about its semantics.
- 4 is the read-only probe. Without it, every "look at the screen" forces a write-op tool call — bad agent ergonomics and unsafe.
- 5 is the meta-tool for multi-turn co-working. Folds 1-G memory, app registry, and the safety kill switch into one knob.

Capabilities **never exposed at the MCP boundary**: `screenshot`, `click`,
`type`, `hotkey`, `scroll`, `find_window`, `parse_screen`, `launch_app`. They
remain importable Python utilities for handler modules and tests.

## Non-goals for this iteration

- Remote MCP transports (HTTP/SSE, WebSocket). stdio only — remoting is solved
  by tunneling stdio through Tailscale-secured SSH (per spec Q2).
- Server-side authentication. The transport boundary is the security boundary.
- Resources or Prompts (the other two MCP capability types). Tools only.
