---
mirrors: tests/windows/test_safety.py
last_updated: 2026-04-25
status: active
---

# test_safety

## Purpose
Tests for the **test-safety layer** in `phone_agent/windows/safety.py` — the runtime that gives integration tests a kill-switch hotkey, presence detection, and a startup countdown. This is infrastructure that protects the user during live-input integration runs.

## Approach
Most parts are platform-independent and tested everywhere:

- **`HotkeyParserTests`** — `_parse_hotkey('shift+right')` → `(MOD_SHIFT, VK_RIGHT)`; rejects empty/modifier-only/two-main-keys/unknown specs.
- **`StateRegistrationTests`** — `register_process` / `register_cleanup` append correctly.
- **`CountdownTests`** — countdown banner writes the right phrases ("take over this machine", hotkey label, countdown).
- **`PresenceMonitorTests`** — patches `_idle_ms` to simulate idle / fresh-input / sustained-input; verifies pause-and-resume vs. abort behaviour.
- **`KillSwitchUnitTests`** — `_fire()` aborts state, kills registered procs, runs cleanup callbacks, calls `os._exit(130)`. Patches `_release_modifier_keys`, `_recenter_cursor`, `os._exit` so the test process survives.

`WindowsOnlyTests` (skipped elsewhere) smoke-checks `_idle_ms` and `KillSwitch.start()/stop()` with an unlikely hotkey combo.

## Status
All passing.

## Known Bugs
None.

## Linked Docs
- Source: `phone_agent/windows/safety.py`
- Consumed by: [conftest.md](conftest.md) (session-wide kill switch + presence monitor)
