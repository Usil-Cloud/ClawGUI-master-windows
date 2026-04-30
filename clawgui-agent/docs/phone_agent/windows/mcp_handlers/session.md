---
mirrors: phone_agent/windows/mcp_handlers/session.py
last_updated: 2026-04-30
status: active
---

# session

## Purpose

Implements `manage_session`: co-working session control surface. One tool,
one `op` argument, six operations. Owns the multi-turn / cross-call state
that the other four tools shouldn't carry on their argument lists.

## Approach

`op` ∈ `{"list_apps", "close_app", "save_memory", "load_memory", "reset", "kill_switch"}`.

- `list_apps` — `app_registry.list_running()`
- `close_app` — `app_resolver.close_app(name)` then registry update
- `save_memory` / `load_memory` — `memory.step_memory` snapshot/restore
- `reset` — close all agent-spawned apps, clear step memory
- `kill_switch` — invoke `windows.safety` immediate halt

## Status

Stub — returns canned SessionResult.

## Known Bugs

None.

## Linked Docs

- Parent: `docs/features/mcp_server/_index.md`
- Step memory: feature 1-G (not started)
- Safety: `docs/phone_agent/windows/safety.md` (pending)
