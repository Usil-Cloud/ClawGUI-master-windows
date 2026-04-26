---
name: Phase 1-D Window Manager hub
description: Parent doc for Feature 1-D — enumerate, focus, minimize/maximize/close windows.
type: project
last_updated: 2026-04-25
status: active
---

# Feature 1-D — Window Manager

**Phase 1, ID 1-D.** Source: `phone_agent/windows/window_manager.py`. Phase role: enumerate and focus windows so the agent can target the right app before issuing GUI actions.

## Children

| Doc | Purpose |
|-----|---------|
| [overview.md](overview.md) | What the feature does, public API, scope |
| [design.md](design.md) | Two-step focus strategy, dataclasses, remote-mode delegation, edge cases |
| [bugs.md](bugs.md) | Bug tracker (anchors per bug) |

## Source files

- `phone_agent/windows/window_manager.py` — implementation
- `tests/windows/test_window_manager.py` — unit + integration tests · doc: [docs/tests/windows/test_window_manager.md](../../tests/windows/test_window_manager.md)
- `tests/windows/test_multi_app_integration.py` — cross-app integration tests · doc: [docs/tests/windows/test_multi_app_integration.md](../../tests/windows/test_multi_app_integration.md)

## Status

| Item | Status |
|------|--------|
| `list_windows` | ✅ stable |
| `focus_window` | ✅ stable (two-step Electron-friendly strategy) |
| `minimize_window` | ✅ stable |
| `maximize_window` | ✅ stable |
| `close_window` | ✅ stable (WM_CLOSE → 0.5s grace → TerminateProcess fallback) |
| Remote-mode WAS delegation | ✅ shape-tested via mocks; awaits real WAS (Phase 3) for end-to-end |
| Unit tests | ✅ all passing |
| Integration tests (Notepad) | ✅ all passing on Windows + pywin32 |
| Multi-app integration (Notepad + Discord + VS Code) | ✅ all passing on dev machine |

## Definition of Done (from roadmap)

- [x] `list_windows()` returns at least the currently open windows with correct titles and hwnd values
- [x] `focus_window('note')` (partial, lowercase) brings Notepad to the foreground and returns `True`
- [x] `focus_window('nonexistent_xyz')` returns `False` without raising an exception
- [x] `minimize_window` and `maximize_window` change the window state as expected on Windows 10/11

**1-D is feature-complete.** Currently in test-hardening phase (more cross-app coverage, edge cases).

## Open work / next steps

_None tracked. Add as bugs surface — see [bugs.md](bugs.md)._

## Related

- Parent roadmap: `Project Ready Player/ClawGUI_Phase1_Roadmap.docx` (Phase 1)
- Sibling features: 1-A Screenshot, 1-B Device Actions, 1-C Keyboard Input
