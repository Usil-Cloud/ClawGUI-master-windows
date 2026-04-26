---
mirrors: tests/windows/test_input.py
last_updated: 2026-04-25
status: active
---

# test_input

## Purpose
Tests for **Feature 1-C Keyboard Input** (`phone_agent/windows/input.py`). Covers `type_text` (ASCII + Unicode clipboard fallback), `hotkey`, `press_key`, `clear_text`, plus remote WAS delegation.

## Approach
- **`MockedInputTests`** — stubs `pyautogui`, `win32clipboard`. ASCII path → `typewrite`; non-ASCII → opens clipboard, `EmptyClipboard`, `SetClipboardData(CF_UNICODETEXT, …)`, `CloseClipboard`, then `hotkey('ctrl','v')`. Verifies `CloseClipboard` runs even when `SetClipboardData` raises. Has a `pyperclip` fallback test for when `win32clipboard` is missing.
- **`IntegrationInputTests`** — Windows + pyautogui + pywin32. Reuses session-shared Notepad; clears via `Ctrl+A` / Delete; reads back via clipboard (`Ctrl+A` → `Ctrl+C` → `GetClipboardData`). Pre-clears clipboard before reads to avoid stale-content false positives. Tests ASCII, numbers/symbols, Unicode (Héllo Wörld), emoji.
- Remote tests assert the right WAS endpoints: `/api/action/type`, `/api/action/hotkey`, `/api/action/press_key`, `/api/action/clear_text`.

## Status
All passing.

## Known Bugs
None.

## Linked Docs
- Source: `phone_agent/windows/input.py`
- Cross-app coverage: [test_multi_app_integration.md](test_multi_app_integration.md)
- Test wiring: [conftest.md](conftest.md)
