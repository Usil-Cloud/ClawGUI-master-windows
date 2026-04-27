---
name: Multi-App Integration hub
description: Parent doc for the cross-app integration test suite covering Features 1-C and 1-D against Notepad, Discord, and VS Code.
type: project
last_updated: 2026-04-27 (added app_registry — Bug 3/4 fix)
status: active
---

# Multi-App Integration Tests

**Cross-cutting test suite.** Exercises Features 1-C (keyboard input) and 1-D (window manager) together across three diverse app types: Notepad (native Win32), Discord (Electron), and VS Code (Electron + Monaco editor).

## Children

| Doc | Purpose |
|-----|---------|
| [overview.md](overview.md) | What the suite covers, app targets, capability gates |
| [design.md](design.md) | Module fixture strategy, teardown, app-resolver subclassing, stub ordering |
| [app_registry.md](app_registry.md) | PID-scoped registry — distinguishes test-owned from user-owned apps (Bug 3 / Bug 4 fix) |
| [bugs.md](bugs.md) | Bug tracker (anchors per bug) |

## Source files

- `tests/windows/test_multi_app_integration.py` — full test suite · companion doc: [docs/tests/windows/test_multi_app_integration.md](../../tests/windows/test_multi_app_integration.md)

## Features under test

| Feature | ID | What's exercised |
|---------|----|-----------------|
| Keyboard Input | 1-C | `type_text`, `hotkey`, `press_key`, `clear_text` in Notepad; smoke tests in Discord and VS Code |
| Window Manager | 1-D | `list_windows`, `focus_window` cycling across all three apps |

## Status

| Item | Status |
|------|--------|
| Notepad — keyboard (type, hotkey, clear) | _placeholder_ |
| Notepad — window (list, focus) | _placeholder_ |
| Discord — window + keyboard smoke tests | _placeholder_ |
| VS Code — window + keyboard smoke tests | _placeholder_ |
| Module fixture (open/close lifecycle) | _placeholder_ |

## Definition of Done

- [ ] All `MultiAppWindowTests` pass with all three apps open simultaneously
- [ ] All `MultiAppKeyboardTests` pass; Notepad clipboard readback is exact-match
- [ ] Discord and VS Code tests skip cleanly when apps are not installed/in PATH
- [ ] No window state leaks between test methods (clear before each write)
- [ ] tearDownModule closes only the test-opened windows; user's own windows unaffected

## Open work / next steps

_See [bugs.md](bugs.md) for tracked issues. Fill in as observations are reported._

## Related

- Feature 1-C doc: _pending_ (`docs/features/keyboard_input/`)
- Feature 1-D doc: [docs/features/window_manager/_index.md](../window_manager/_index.md)
- Single-app test docs: [test_window_manager.md](../../tests/windows/test_window_manager.md), [test_input.md](../../tests/windows/test_input.md)
