---
name: Multi-App Integration overview
description: What the cross-app integration suite covers, which apps it targets, and how capability gating works.
type: project
last_updated: 2026-04-27
status: active
---

# Multi-App Integration — Overview

## Purpose

Verify that the Phase 1 primitives (keyboard input and window management) work correctly across **three structurally different app types** in a single test run, without state leaking between apps or between test methods.

## App targets

| App | Window type | Capability gate | Skip condition |
|-----|-------------|-----------------|----------------|
| Notepad | Native Win32 | `_ON_WINDOWS and _HAS_WIN32` | Non-Windows or no pywin32 |
| Discord | Electron | `_HAS_DISCORD` | `%LOCALAPPDATA%\Discord` absent |
| VS Code | Electron + Monaco | `_HAS_VSCODE` | `code` not in PATH |

Discord and VS Code tests skip individually (not the whole module) when their app is absent.

## Test classes

### `MultiAppWindowTests` — Feature 1-D

Covers `list_windows` and `focus_window` across all three apps.

| Group | Tests |
|-------|-------|
| `list_windows` | App windows appear in result; all entries visible; titles non-empty; hwnds positive and distinct; rects are 4-tuples |
| `focus_window` | Exact and partial/lowercase matches return `True`; foreground title matches after call; cycle Notepad → Discord; cycle all three; nonexistent returns `False` without raising |

### `MultiAppKeyboardTests` — Feature 1-C

Uses Notepad as the ground-truth verifier (clipboard read-back). Discord and VS Code are smoke targets only — no content assertion.

| App | Tests |
|-----|-------|
| Notepad | ASCII, numbers+symbols, Unicode type; Enter creates newline; `clear_text` empties; Ctrl+A selects all |
| Discord | Ctrl+K opens quick-switcher (no raise); `type_text` into search (no raise); Escape dismisses (no raise) |
| VS Code | `type_text` ASCII into new untitled file with clipboard verify; Ctrl+Shift+P opens command palette (no raise); Escape dismisses palette (no raise) |

## Capability flags

```python
_ON_WINDOWS    = platform.system() == "Windows"
_HAS_WIN32     = bool(real pywin32 importable)
_HAS_PYAUTOGUI = bool(real pyautogui importable)
_HAS_DISCORD   = _ON_WINDOWS and Path(%LOCALAPPDATA%/Discord).is_dir()
_HAS_VSCODE    = bool(shutil.which("code"))
```

Flags are evaluated **before** stubs are installed so a stub cannot falsely satisfy a capability check.

Two skip guards derived from flags:

- `_WIN_SKIP` — skips `MultiAppWindowTests` entirely (requires Windows + pywin32)
- `_KB_SKIP` — skips `MultiAppKeyboardTests` entirely (requires Windows + pywin32 + pyautogui)
