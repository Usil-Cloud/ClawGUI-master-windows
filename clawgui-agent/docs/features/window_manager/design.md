---
name: Window Manager design notes
description: Key decisions — two-step focus, close fallback, error handling.
type: project
last_updated: 2026-04-25
status: active
---

# Window Manager — Design Notes

## 1. Two-step focus strategy (Electron / CEF compatible)

**Problem.** A bare `SetForegroundWindow(hwnd)` is unreliable when an Electron app (VS Code, Discord) currently holds foreground — Windows enforces foreground-lock rules that let the active app refuse focus changes from background processes. `SetForegroundWindow` returns `True` but the window does not actually come forward.

**Solution in `_local_focus`** (`window_manager.py:74-113`):

1. **`AttachThreadInput`** — attach the current foreground thread's input queue to the target's thread. This transfers the foreground-lock right.
2. **TOPMOST flip** — `SetWindowPos(HWND_TOPMOST)` then `SetWindowPos(HWND_NOTOPMOST, SHOWWINDOW)`. Promoting then demoting wins the z-order contest even if the previous owner reclaims focus, because the demotion lands the window as the top normal window.
3. `BringWindowToTop` + `SetForegroundWindow` — finalize.
4. `AttachThreadInput(..., False)` in `finally` — always detach.

Before the focus calls, if `IsIconic(hwnd)` is true, `ShowWindow(hwnd, SW_RESTORE)` un-minimizes it.

## 2. Close: WM_CLOSE → grace → TerminateProcess

**Problem.** `WM_CLOSE` is polite — apps can intercept it and pop a "save changes?" dialog. The window then stays alive and the test can't proceed.

**Solution in `_local_set_window_state(state="close")`** (`window_manager.py:159-179`):

```
PostMessage(hwnd, WM_CLOSE)
sleep(0.5)
if IsWindow(hwnd):
    _kill_window_process(hwnd)   # OpenProcess(PROCESS_TERMINATE) + TerminateProcess
```

`_kill_window_process` (`window_manager.py:136-156`) resolves the owning PID via `GetWindowThreadProcessId`, opens the process with `PROCESS_TERMINATE`, calls `TerminateProcess`, and closes the handle. Wrapped in `try/except` — silent on failure (we already tried the polite path).

## 3. Error handling philosophy

Every `_local_*` helper is wrapped in `try/except Exception` and returns `False` (or `[]` for `list_windows`) on any failure. **Rationale:** the agent loop must not crash on a transient win32 error — it can retry, fall back, or log. Callers check the boolean.

Trade-off: silent failures can mask bugs. Mitigated by integration tests that assert real state changes (e.g. `IsIconic` after `minimize_window`, `GetWindowPlacement[1] == SW_SHOWMAXIMIZED` after `maximize_window`).

## 4. Lazy imports

`win32gui` / `win32con` / `win32process` / `win32api` are imported **inside** each helper, not at module top. Two reasons:

1. The module imports cleanly on non-Windows for static checks and partial test runs.
2. Tests can patch `sys.modules["win32gui"]` between calls without re-importing the module.

Test stubs in `tests/windows/test_window_manager.py:55-71` rely on this — they install fake modules before the first import of `window_manager`.

## 5. Remote-mode delegation

Each public function checks `is_local(device_id)` first. Local → `_local_*`. Remote → `post(device_id, "/api/...", payload)`. Remote responses are minimal:

- `list_windows`: `{"windows": [{"hwnd": int, "title": str, "visible": bool, "rect": [l,t,r,b]}, ...]}`
- focus / min / max / close: `{"ok": bool}`

The unit tests cover the request shape; end-to-end remote validation waits on Phase 3 (WAS) to come online.

## 6. Why `EnumWindows` order is good enough

We don't sort or rank matches — first hit wins. For ClawGUI's use case (single instance of a target app at a time), this is fine. If multi-instance disambiguation becomes a need (e.g., two Notepad windows), we'd add a `match_index` or `pid_filter` parameter rather than guessing.
