---
mirrors: tests/windows/test_screenshot.py
last_updated: 2026-04-25
status: active
---

# test_screenshot

## Purpose
Tests for **Feature 1-A Windows Screenshot** (`phone_agent/windows/screenshot.py`). Verifies the four auto-mode scenarios for `get_screenshot(focus_apps=...)` plus `get_screen_size`, the `Screenshot` dataclass, and graceful fallback when `mss` is unavailable.

## Approach
Two test classes:

- **`MockedScreenshotTests`** — patches `sys.modules["mss"]` with a fake context-manager whose `grab()` returns a fake image of the requested dimensions. Patches `_find_window` to control the "window found / not found / minimised" branches. Verifies mode selection (`window` vs `full`) and dataclass invariants.
- **`IntegrationScreenshotTests`** — Windows-only, requires `mss` + `pywin32`. Reuses session-shared Notepad. Decodes the returned base64 PNG via PIL and asserts dimensions match the actual monitor / window.

## Status
All passing on Windows with deps. Mocked tests run cross-platform.

## Known Bugs
None.

## Linked Docs
- Source: `phone_agent/windows/screenshot.py`
- Test wiring: [conftest.md](conftest.md)
