---
mirrors: tests/windows/test_multi_app_integration.py
last_updated: 2026-04-25
status: active
---

# test_multi_app_integration

## Purpose
Cross-app integration tests for **Features 1-C (keyboard) and 1-D (window manager)** running against Notepad + Discord + VS Code simultaneously. Verifies primitives work across diverse app types (native Win32, Electron, Electron+Monaco).

## Approach
Module-level `setUpModule` opens all three apps; `tearDownModule` closes each by hwnd-targeted `WM_CLOSE` then process kill (so unrelated user windows of the same app aren't touched). Notepad is re-used from session-shared fixture in `conftest._shared_notepad` — never killed at module teardown.

Capability detection runs **before** stub installation so real `pywin32` / `pyautogui` are detected correctly. Discord is probed via `%LOCALAPPDATA%\Discord` to skip cleanly when not installed. VS Code via `shutil.which("code")`.

Discord launches through a subclassed `AppResolver` that disables tier 5 (Start Menu) — opening the Start Menu mid-test would be disruptive.

Two test classes:
- **`MultiAppWindowTests`** — `list_windows` / `focus_window` cycle across all apps; verifies foreground after focus.
- **`MultiAppKeyboardTests`** — `type_text` / `hotkey` / `press_key` / `clear_text`; Notepad is the verifier (read back via clipboard); Discord & VS Code are smoke tests (Ctrl+K quick-switcher, Ctrl+Shift+P palette).

## Status
All passing on dev machine with all three apps installed.

## Known Bugs
None.

## Linked Docs
- Parent (1-D): [docs/features/window_manager/_index.md](../../features/window_manager/_index.md)
- Single-app variants: [test_window_manager.md](test_window_manager.md), [test_input.md](test_input.md)
- Test wiring: [conftest.md](conftest.md)
