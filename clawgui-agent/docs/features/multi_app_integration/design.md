---
name: Multi-App Integration design
description: Module fixture strategy, app lifecycle, teardown approach, stub ordering, and key design decisions.
type: project
last_updated: 2026-04-27
status: active
---

# Multi-App Integration — Design

## Module fixture (open once, share across all tests)

All three apps are opened in `setUpModule` and closed in `tearDownModule`. This avoids per-test app spawn/kill overhead, which would make the suite impractically slow for Electron apps (Discord start: ~10–30 s).

```
setUpModule
  ├── Reuse session-shared Notepad from conftest._shared_notepad[0]
  │     └── Falls back to subprocess.Popen(["notepad.exe"]) if conftest absent
  ├── Discord: _launch_discord() → _wait_for_window("Discord", timeout=30)
  └── VS Code: subprocess.Popen(["code", "--new-window"]) → _wait_for_window("Visual Studio Code", timeout=15)

tearDownModule
  ├── Discord: PostMessage(hwnd, WM_CLOSE) → 0.5s grace → _kill_window_process(hwnd)
  ├── VS Code: same hwnd-targeted strategy
  └── Notepad: only killed if NOT the session-shared fixture
```

hwnd capture at startup (`_discord_hwnd`, `_vscode_hwnd`) ensures teardown targets only the test-opened windows, not any user windows of the same app.

## Discord launch — tier 5 exclusion

Discord is resolved via `AppResolver` (tiers 1–4). Tier 5 (Start Menu via `pyautogui.hotkey("win")`) is excluded by subclassing:

```python
class _NoStartMenuResolver(AppResolver):
    def _tier5_startmenu(self, app_name: str):
        return None
```

Rationale: tier 5 actually opens the Start Menu as a side-effect, which is visually disruptive and can steal focus mid-test.

## Stub ordering constraint

Capability flags (`_HAS_WIN32`, `_HAS_PYAUTOGUI`) are evaluated first, then `_stub_if_missing()` is called. The `_stub_if_missing` helper only installs a stub when the real import fails — so real pywin32 is always preferred over the stub. If stubs ran first, a successful stub import would set `_HAS_WIN32 = True` incorrectly on a machine without real pywin32.

## Clipboard-based Notepad verification

`type_text` output is verified by:
1. `_clear_clipboard()` — empties clipboard before read
2. `pyautogui.hotkey("ctrl", "a")` — select all
3. `pyautogui.hotkey("ctrl", "c")` — copy
4. `_read_clipboard()` — returns `CF_UNICODETEXT` data

This avoids OCR or screen scraping and works reliably for ASCII, digits+symbols, and Unicode.

## Notepad state isolation between tests

Each keyboard test calls `_clear_notepad()` before typing. `_clear_notepad()` calls `inp_mod.clear_text()`, which sends Ctrl+A → Delete. A 0.2 s sleep follows to let Notepad process the deletion before the next `type_text` call.

## Focus-before-type pattern

Every keyboard test helper calls `_focus(partial_title)` (which calls `wm_mod.focus_window`) with a 0.3 s sleep before sending input. This prevents input from landing in the wrong window when test ordering shifts foreground focus.

## Known timing sensitivities

_Placeholder — fill in from observed flakes._
