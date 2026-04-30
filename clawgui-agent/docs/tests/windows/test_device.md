---
mirrors: tests/windows/test_device.py
last_updated: 2026-04-25
status: active
---

# test_device

## Purpose
Tests for **Feature 1-B Core GUI Actions** (`phone_agent/windows/device.py`). Covers `tap`, `double_tap`, `right_click`, `long_press`, `swipe`, `scroll`, `launch_app`, and `_local_get_current_app`.

## Approach
Two test classes:

- **`MockedDeviceTests`** — stubs `pyautogui` and `win32gui` via `sys.modules`. Verifies each action calls the right pyautogui method with the expected args (`scroll` direction → sign of clicks; `swipe` → `moveTo` then `dragTo`; `long_press` → `mouseDown` / sleep / `mouseUp` with the correct duration). Also tests `launch_app` fall-through: known name → `subprocess.Popen`; unresolved → `AppResolver.resolve` returns None → `False`; subprocess failure → Start Menu hotkey fallback.
- **`IntegrationDeviceTests`** — Windows + pyautogui + pywin32. All cursor moves stay near (100, 100); `long_press` capped at 200 ms; `pyautogui.FAILSAFE` on. Smoke-tests every action and verifies `launch_app('Notepad')` actually opens Notepad.

## Status
All passing.

## Known Bugs
None.

## Linked Docs
- Source: `phone_agent/windows/device.py`
- Helper test: [test_app_resolver.md](test_app_resolver.md) (app launch resolution chain)
- Test wiring: [conftest.md](conftest.md)
