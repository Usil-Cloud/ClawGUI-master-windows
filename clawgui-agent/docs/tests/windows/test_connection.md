---
mirrors: tests/windows/test_connection.py
last_updated: 2026-04-26
status: active
---

# test_connection

## Purpose
Phase 1-E unit tests for `phone_agent/windows/connection.py`. Verifies
`detect_mode`, `verify_connection`, `get_connection`, and `forward_action`
behavior end-to-end with mocked `urllib.request.urlopen`.

## Approach
- All HTTP is mocked via `patch.object(cx._urlreq, "urlopen", ...)` — no real
  network is touched, so the suite is OS-independent and CI-safe.
- A small `_fake_resp(body, status)` helper builds context-manager objects
  that mimic `urlopen`'s return value.
- `requests` is stubbed at module-import time so the test file loads on
  machines where `requests` isn't installed (the legacy half of `connection.py`
  imports it at top level).

### Coverage matrix

| Function           | Cases                                                            |
|--------------------|------------------------------------------------------------------|
| `detect_mode`      | `None`, `'local'`, `''`, `host:port`, bare host, `http://` prefix|
| `verify_connection`| healthy 200, URLError, timeout, non-200, malformed JSON          |
| `get_connection`   | local short-circuits (urlopen never called), remote healthy, remote unreachable raises `ConnectionError` |
| `forward_action`   | `"click"` → `/api/action/click`, leading-slash custom path, local profile rejected with `ValueError` |

## Status
- ✅ 17/17 passing (Python 3.13, pytest 9.0).
- ✅ Runs on any OS — no Windows or display required.

## Known Bugs
_None._

## Linked Docs
- Source under test: [docs/phone_agent/windows/connection.md](../../phone_agent/windows/connection.md)
- Feature hub: [docs/features/connection_manager/_index.md](../../features/connection_manager/_index.md)
