---
mirrors: phone_agent/windows/mcp_handlers/navigate.py
last_updated: 2026-04-30
status: active
---

# navigate

## Purpose

Implements `navigate_windows`: reach a UI state on the target machine
(open/focus app, click/type/scroll until a goal position is reached). No
completion verification — best-effort.

## Approach

Composes existing capability modules: `app_resolver` (open app), `window_manager`
(focus), `device` (mouse), `input` (keyboard), `screenshot` (final state).
Returns a `NavigateResult` with `final_screenshot_b64`, `active_window`,
`steps_taken`, `notes`.

## Status

Stub — returns canned result.

## Known Bugs

None.

## Linked Docs

- Parent: `docs/features/mcp_server/_index.md`
- Sibling design: `docs/features/mcp_server/design.md`
