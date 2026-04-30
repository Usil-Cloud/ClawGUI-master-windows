---
mirrors: phone_agent/windows/mcp_handlers/inspect.py
last_updated: 2026-04-30 (implemented end-to-end)
status: active
---

# inspect

## Purpose

Implements `inspect_screen`: a read-only probe. Returns a screenshot plus
a structured GUI-Owl screen parse so the client can decide whether to act.
Cheapest of the five tools — no input is dispatched.

## Approach

Wraps `windows.screenshot.get_screenshot` and (when `parse=True`) calls
`perception.gui_owl_adapter.analyze`. Returns `InspectResult` with
`screenshot_b64`, `screen_state` (or `None` when `parse=False`).

## Status

Implemented end-to-end. Composed from:
- `window_manager.focus_window` (best-effort, non-fatal on False)
- `screenshot.get_screenshot` (fallback to full-monitor on any error)
- `win32gui.GetForegroundWindow` for active window title
- `GUIOwlAdapter.analyze` (non-fatal fallback state on adapter error)

`screen_state` omits `raw_response` to keep MCP response size bounded.
Fallback details surface in `notes` instead.

## Known Bugs

None.

## Linked Docs

- Parent: `docs/features/mcp_server/_index.md`
- Perception: `docs/features/gui_owl_perception/_index.md`
