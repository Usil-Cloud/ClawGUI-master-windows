---
mirrors: phone_agent/windows/connection.py
last_updated: 2026-04-26
status: active
---

# Connection Manager — Overview

## What
Decide at startup whether the agent should call Windows libraries directly
(local mode) or forward each action over HTTP to a remote Windows Agent
Server (remote mode). Callers receive a `ConnectionProfile` and don't branch
on the choice themselves.

## Why
Phase 1 must work both for "agent on the same Windows box as the target apps"
and "agent running elsewhere, controlling a remote Windows machine." Putting
the local/remote decision behind one dataclass means feature modules
(`device.py`, `window_manager.py`, `screenshot.py`, …) only have to ask
`is this local?` once, not redesign their public API.

## Public API (Phase 1-E spec)

```python
from phone_agent.windows.connection import (
    ConnectionProfile,   # dataclass(host, port, mode)
    detect_mode,         # device_id -> ConnectionProfile  (pure)
    verify_connection,   # (host, port, timeout=3) -> bool
    get_connection,      # device_id -> ConnectionProfile  (verifies remote)
    forward_action,      # (profile, endpoint, payload) -> dict
)
```

### Device-id formats accepted by `detect_mode`

| Input                          | Result                                        |
|--------------------------------|-----------------------------------------------|
| `None`, `''`, `'local'`        | `ConnectionProfile('localhost', 0, 'local')`  |
| `'192.168.1.5:7860'`           | `('192.168.1.5', 7860, 'remote')`             |
| `'10.0.0.7'` (no port)         | `('10.0.0.7', 7860, 'remote')`                |
| `'http://host:9000/'`          | `('host', 9000, 'remote')`                    |

## Scope
- **In scope:** mode detection, health probe, action forwarding.
- **Out of scope:** the WAS server itself (Phase 3-A), authentication,
  retries with backoff, connection pooling.

## Linked Docs
- Hub: [_index.md](_index.md)
- Source doc: [../../phone_agent/windows/connection.md](../../phone_agent/windows/connection.md)
- Test doc: [../../tests/windows/test_connection.md](../../tests/windows/test_connection.md)
- Design notes: [design.md](design.md)
- Bugs: [bugs.md](bugs.md)
