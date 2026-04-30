---
mirrors: tests/windows/test_window_manager.py
last_updated: 2026-04-25
status: active
---

# test_window_manager

## Purpose
Tests for **Feature 1-D Window Manager** (`phone_agent/windows/window_manager.py`). Validates `list_windows`, `focus_window`, `minimize_window`, `maximize_window`, `close_window`, plus their remote-mode (`is_local=False`) delegation to the Windows Agent Server.

## Approach
Two test classes:

- **`MockedWindowManagerTests`** — runs anywhere. Uses `_stub_if_missing` to plant stub `win32gui` / `win32con` in `sys.modules` before importing `window_manager`, so production-side lazy imports pick up the mocks. Each test re-patches via `patch.dict("sys.modules", ...)`.
- **`IntegrationWindowManagerTests`** — `@skipIf` non-Windows or no `pywin32`. Reuses the session-shared Notepad from `conftest._shared_notepad` (or spawns its own), exercises real `list_windows`/`focus_window`/`minimize`/`maximize`, and restores window state between tests.

Remote tests patch `wm.is_local` and `wm.post` to assert the right WAS endpoints get called: `/api/windows/list`, `/api/action/focus_window`, `/api/windows/minimize|maximize|close`.

## Status
- All unit tests passing.
- Integration tests run on Windows + pywin32; otherwise skipped with reason.

## Known Bugs
- **test_minimize_window_changes_window_state** was flaky on Windows 11 new Notepad: `IsIconic` returned 0 even when the window was visually minimized. Root causes: (1) the previous maximize tests left the window in maximized state because `_local_focus` only called `SW_RESTORE` for iconic windows; (2) `IsIconic` is unreliable for modern XAML/UWP-style apps. Fixed by: restoring from maximized state in `_local_focus`, switching assertion to `GetWindowPlacement().showCmd == SW_SHOWMINIMIZED`, and increasing post-minimize sleep to 0.8 s.

## Linked Docs
- Parent: [docs/features/window_manager/_index.md](../../features/window_manager/_index.md)
- Source: `phone_agent/windows/window_manager.py`
- Related test: [test_multi_app_integration.md](test_multi_app_integration.md) (cross-app focus)
- Test wiring: [conftest.md](conftest.md)
