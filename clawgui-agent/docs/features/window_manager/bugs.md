---
name: Window Manager bug tracker
description: Bug log for Feature 1-D. Anchors per bug for cross-linking from source.
type: project
last_updated: 2026-04-25
status: active
---

# Window Manager — Bug Tracker

How to use:
- New bug → add a `## Bug N — short title` section below with the anchor `bug-N`.
- Source files referencing a bug should add `# Bug tracker: docs/features/window_manager/bugs.md#bug-N` to their header.
- When fixed, change the status line and keep the entry as history.

---

<!--
Template:

## Bug 1 — short title  {#bug-1}

**Status:** open · **Severity:** medium · **Reported:** 2026-04-25

**Symptom(s).** What goes wrong, observable behaviour.

**Repro.**
1. Step
2. Step

**Where.** `phone_agent/windows/window_manager.py:NNN` (function name)

**Suspected cause.** Hypothesis.

**Fix / workaround.** What we did, or what's blocking.
-->


## Bug 1 — test_window_manager failure  {#bug-1}

**Status:** fixed · **Severity:** medium · **Reported:** 2026-04-25 · **Fixed:** 2026-04-25

**Symptom(s).**
Two tests failed when running `python -m pytest tests/windows/test_window_manager.py -v`:
- `MockedWindowManagerTests::test_focus_window_restores_minimized_window` — "Expected ShowWindow called once. Called 0 times."
- `IntegrationWindowManagerTests::test_minimize_window_changes_window_state` — "Expected minimized (2), got 1."

**Root causes.**
1. **Unit test:** `_local_focus` was updated to use `GetWindowPlacement` instead of `IsIconic`, but `_win32con_mock()` was missing `SW_SHOWMINIMIZED`/`SW_SHOWMAXIMIZED` constants and the test never configured `g.GetWindowPlacement.return_value`. So `placement[1]` was a bare MagicMock that never matched either constant → `ShowWindow` was never called.
2. **Integration test:** Multiple Notepad windows are alive in some runs (leftover processes). The verification `EnumWindows` callback found a *different* Notepad hwnd than the one `_find_hwnd` minimized → placement on the wrong window returned SW_SHOWNORMAL.

**Fix.**
- Added `SW_SHOWMINIMIZED = 2` and `SW_SHOWMAXIMIZED = 3` to `_win32con_mock()`.
- In `test_focus_window_restores_minimized_window`, set `g.GetWindowPlacement.return_value = (0, c.SW_SHOWMINIMIZED, 0, ...)` so the condition fires.
- In `test_minimize_window_changes_window_state`, capture `target_hwnd = wm._find_hwnd("Notepad")` **before** minimizing and verify that exact hwnd's placement instead of re-enumerating (which could pick up a different window).

All 39 tests pass after the fix.
