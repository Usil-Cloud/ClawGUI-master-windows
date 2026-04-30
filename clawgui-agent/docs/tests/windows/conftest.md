---
mirrors: tests/windows/conftest.py
last_updated: 2026-04-25
status: active
---

# conftest

## Purpose
Pytest wiring for every Windows test session. Provides three session-scoped autouse fixtures and the shared Notepad handle used by `test_window_manager`, `test_input`, `test_screenshot`, and `test_multi_app_integration`.

## Approach
- **`_safety_session`** — wraps the session in `safety.safety_session()` → installs the kill-switch hotkey (`Shift+Right`, override via `CLAWGUI_KILL_HOTKEY`), shows the 3-2-1 countdown, restores cursor + modifier keys on abort.
- **`_shared_notepad_session`** — opens **one** Notepad per session, registers it with `safety.register_process`, and exposes the `Popen` via the module-level `_shared_notepad: list = [None]`. Other test files import `from conftest import _shared_notepad` and reuse `_shared_notepad[0]` instead of spawning their own — keeps Notepad count to 1 even when many test classes need it.
- **`_presence_monitor`** — per-test autouse. Before each test runs, calls `pm.wait_for_idle_or_abort()` (pauses if the user touched mouse/kbd during the previous test). Records test nodeid in `safety.STATE.current_step`.

`CLAWGUI_TEST_SAFETY=0` bypasses the safety layer entirely (CI use).

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Safety module: [test_safety.md](test_safety.md)
- All test files in this folder consume `_shared_notepad`.
