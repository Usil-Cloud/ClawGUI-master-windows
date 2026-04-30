---
mirrors: phone_agent/windows/connection.py
last_updated: 2026-04-26
status: active
---

# connection

## Purpose
Decide whether the agent runs in **local mode** (direct library calls on this
machine) or **remote mode** (HTTP to a Windows Agent Server). The split is
transparent to callers — they get a `ConnectionProfile` and don't branch on it
themselves.

## Approach
Phase 1-E spec API:

- `ConnectionProfile(host, port, mode)` — dataclass; `mode` is `'local'` or `'remote'`. Local profiles use `host='localhost'`, `port=0` as sentinels.
- `detect_mode(device_id)` — pure mapping. `None` / `''` / `'local'` → local. `'host:port'` or bare `'host'` → remote (default port 7860). Strips `http://` / `https://` and trailing slashes.
- `verify_connection(host, port, timeout=3) → bool` — health probe via `GET /api/info`. Returns True iff the response is JSON containing a `machine` key. Swallows `URLError`, `TimeoutError`, `OSError`, and `ValueError` — never raises on unreachable hosts (per DoD).
- `get_connection(device_id) → ConnectionProfile` — calls `detect_mode`, then verifies remote profiles. Raises `ConnectionError` if a remote target is unreachable.
- `forward_action(profile, endpoint, payload) → dict` — POSTs JSON to a remote WAS. `endpoint` is the bare action name (`"click"` → `/api/action/click`); a leading slash escapes the prefix for custom paths. Raises `ValueError` if called with a local profile.

The new API uses **stdlib `urllib`** only — no third-party HTTP dependency on
the spec path.

### Legacy helpers (Phase 1-A..1-D)
The previous helpers are retained verbatim so already-shipped modules keep
working: `is_local`, `get_was_url`, `post`, `get`, `verify_device_info`
(renamed from the original `verify_connection`), `list_devices`,
`WindowsConnection`, `DeviceInfo`, `ConnectionMode`. These still use the
`requests` library.

The Phase 1-E `verify_connection` (bool, takes host+port) replaces the old
function of the same name. Callers needing the rich `DeviceInfo` should use
`verify_device_info(device_id)` instead.

## Status
- ✅ Phase 1-E spec API implemented and unit-tested (17 tests, all green).
- ✅ Legacy helpers preserved; `WindowsConnection.connect` updated to use
  `verify_device_info`.
- ⏳ Real WAS endpoint (`GET /api/info`) ships in Phase 3-A. Until then, only
  mocked HTTP is exercised.

## Known Bugs
_None._

## Linked Docs
- Parent: [docs/features/connection_manager/_index.md](../../features/connection_manager/_index.md)
- Tests:  [docs/tests/windows/test_connection.md](../../tests/windows/test_connection.md)
