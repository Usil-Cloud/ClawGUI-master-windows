---
mirrors: phone_agent/windows/mcp_handlers/build.py
last_updated: 2026-04-30
status: active
---

# build

## Purpose

Implements `build_with_claw`: execute a goal end-to-end with a
plan → act → re-perceive → judge → retry loop. Returns a transcript and a
pass/fail verdict.

## Approach

- Calls into `navigate.py` for execution steps.
- Calls into `perception.gui_owl_adapter` for screen parses.
- Calls a server-side LLM (configured via `config/endpoints.py`) to plan steps and judge "is goal complete?". Per spec Q2-A, the server owns the verify step — not the MCP client.
- Bounded by `max_iterations` (default 5) to prevent runaway loops.
- Persists transcript to `memory.step_memory` so `manage_session` can resume mid-build.

## Status

Stub — returns canned BuildResult.

## Known Bugs

None.

## Linked Docs

- Parent: `docs/features/mcp_server/_index.md`
- Verify loop pseudocode: `docs/features/mcp_server/design.md`
