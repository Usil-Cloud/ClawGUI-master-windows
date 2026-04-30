---
name: App Registry — design doc
description: PID-scoped registry that distinguishes test-spawned apps (closeable) from user-owned apps (never touched), with cross-run persistence.
type: project
last_updated: 2026-04-27
status: active
---

# App Registry

Source: [`phone_agent/windows/app_registry.py`](../../../phone_agent/windows/app_registry.py)

## Purpose

Two failure modes drove this module:

* **Bug 3** ([bugs.md#bug-N](bugs.md#bug-N)) — re-running an integration test
  spawned a duplicate of every app on each run. Root cause: setUp called
  `subprocess.Popen` unconditionally with no awareness of instances spawned by
  earlier runs.
* **Bug 4** ([bugs.md#bug-4](bugs.md#bug-4)) — name-based teardown
  (`find hwnd whose title contains "Visual Studio Code" → kill its PID`)
  could match the user's own VS Code window and terminate it, destroying
  unsaved work.

The registry replaces *name-based* discovery with *PID-based* discovery.

## Two PID classes

| Class       | Source                                                     | Closeable at teardown? |
|-------------|------------------------------------------------------------|------------------------|
| **OWNED**   | spawned via `spawn()`, OR alive PID reloaded from registry file, OR resolved from a window we waited for via `register_hwnd_pid` | yes |
| **ADOPTED** | pre-existing user processes registered via `adopt_pid` / `adopt_running` / `auto_adopt_from_config` | **never** |

Anything not in either set is invisible — we never act on it.

## Cross-run persistence

`~/.clawgui/app_registry.json` stores `{pid, exe, spawned_at, label}` for
every OWNED process. On session start, `reload_owned_from_disk()` filters to
PIDs that are still alive and re-registers them. This is what lets Bug 3 be
fixed — the next run sees the previous run's still-alive Discord PID and
reuses its window instead of launching a second copy.

Adopted PIDs are **not** persisted — each session re-evaluates the user's
running apps fresh.

## Adoption configuration

Two equivalent paths (both optional):

* Env var `CLAWGUI_ADOPT_APPS="UnrealEditor.exe,obsidian.exe"`
* `~/.clawgui/adopt.json` — `{"adopt": ["UnrealEditor.exe"]}`

`auto_adopt_from_config()` is called once at session setup. For each listed
exe substring it scans every running process and registers matches as
ADOPTED. Test code then uses `find_adopted_pid("UnrealEditor.exe")` before
spawning.

> **Future (Phase 2 GUI-vision):** explicit adopt config will be replaced by
> a screenshot-based scan that recognises apps in the taskbar. Until then
> the config + interactive prompt path is the only mechanism.

## Lifecycle from a test's perspective

```
session start
├── reload_owned_from_disk()           # bring forward last run's still-alive PIDs
├── auto_adopt_from_config()           # register user's pre-opened apps as ADOPTED
│
├── for each app:
│   ├── pid = find_alive_owned_pid(exe) or find_adopted_pid(exe)
│   ├── if pid: hwnd = wait_for_window_with_pid(title, pid)   # reuse
│   └── else:   proc = spawn(label, args)
│                hwnd = wait_for_window(title)
│                register_hwnd_pid(hwnd)                        # capture renderer PID
│
├── ... tests run ...
│
└── teardown:
    └── for each captured hwnd:
        └── safe_close_hwnd(hwnd)  # closes only if pid in OWNED; ADOPTED skipped
```

## Why `register_hwnd_pid` is separate from `spawn`

Electron launchers (notably `code.exe --new-window`) exit immediately after
handing the new-window request to the long-lived `Code.exe` renderer
process. The Popen PID we get from `spawn()` becomes dead within milliseconds
and refers to the wrong process anyway. After we wait for the window, we
resolve the PID from the hwnd and *re-register* that PID as OWNED. That is
the PID we actually need to close at teardown.

## Why `safe_close_hwnd` returns a string

Diagnostics. A run that returns `'skipped'` for an adopted hwnd is the
correct, non-destructive behaviour — but we want it to be visible in test
output, not silent.

## What this module deliberately does not do

* **No process tree walking.** We never kill child processes. If a test
  spawns a launcher that spawns the real app, the test must
  `register_hwnd_pid` the real window so the real PID enters OWNED.
* **No window enumeration.** That belongs to the test or to `window_manager`.
  This module operates on PIDs and hwnds the caller hands it.
* **No error-raising.** Every Win32 call is wrapped — registry failure must
  never cascade into test failure. Diagnostics go through `snapshot()`.

## Open questions / future work

* Hook for a Phase-2 vision adapter to call `adopt_pid` once it identifies
  on-screen apps.
* Re-evaluate whether `auto_adopt_from_config` should run an interactive
  picker when no env / file config is present (Q6 option D — deferred).
* Consider integrating with `phone_agent/windows/safety.py` so the
  kill-switch's emergency teardown also goes through `safe_close_hwnd`
  (currently it calls `proc.kill()` directly on registered Popens).
