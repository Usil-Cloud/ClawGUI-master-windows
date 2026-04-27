---
mirrors: phone_agent/windows/connection.py
last_updated: 2026-04-26
status: active
---

# Connection Manager — Design

## Dataclass shape

```python
@dataclass
class ConnectionProfile:
    host: str       # 'localhost' for local; resolvable host/IP for remote
    port: int       # 0 for local (sentinel); typically 7860 for remote
    mode: Literal['local', 'remote']
```

Rationale for the local sentinels (`'localhost'` + `0`): keeps `host`/`port`
non-Optional so downstream code never has to do `if profile.host is None`.
The mode flag is the one true boolean.

## Mode-detection rules

`detect_mode(device_id)` is intentionally pure — no I/O, no exceptions.
Verification of remote reachability is a separate concern handled by
`verify_connection` / `get_connection`. This makes `detect_mode` cheap to
call from logging, CLI parsing, and config loaders.

Parsing rules (in order):
1. If input is `None`, empty, or `'local'` (case-insensitive) → local.
2. Strip leading `http://` / `https://` and any trailing `/`.
3. If the remainder contains `:`, split into `host:port`. If port can't be
   parsed as int, fall back to `DEFAULT_REMOTE_PORT` (7860).
4. Otherwise treat the whole thing as the host with default port 7860.

## Health probe vs. info fetch

The Phase 1-E spec calls for `verify_connection(host, port) → bool` against
`GET /api/health` returning `{status: 'ok'}`. We diverged on the endpoint
(per Q2 of the spec interview) and reuse the existing `GET /api/info`
contract — that endpoint is already documented in the legacy code path and
will exist in WAS (Phase 3-A) regardless. A response is "healthy" when it
parses as JSON and contains a `machine` key.

Trade-off: a slightly heavier payload than a dedicated `/health`, but no
additional WAS surface area to specify and one fewer thing to mock.

## HTTP library choice

The Phase 1-E spec API uses **stdlib `urllib`** only. Reasons:
- The spec explicitly listed it as the option.
- One fewer third-party dep on the spec path makes future packaging simpler.
- The legacy half of the module (`post`/`get`/`verify_device_info`) keeps
  using `requests` because it's already wired into the Phase 1-A..1-D code
  paths and works fine.

These two HTTP layers are independent and won't be unified until the WAS
server lands and we have a real integration target.

## `forward_action` endpoint shape

Callers pass a bare action name; the function prefixes `/api/action/`. A
leading slash is the escape hatch for non-standard paths
(`forward_action(profile, "/health/probe", ...)`). `ConnectionProfile.mode`
is checked — calling with a local profile is a programmer error and raises
`ValueError`, not `ConnectionError`.

## Coexistence with the legacy API

The original `connection.py` had a function called `verify_connection` with
an entirely different signature (`(device_id) → DeviceInfo`, raises on
failure). Renamed to `verify_device_info` so the spec name is free for the
bool-returning probe. `__init__.py` re-exports both. Phase 1-A..1-D modules
that touched `verify_connection` were already mocking it in tests as
`lambda *a, **kw: True`, so the rename is invisible to them.

## Future / out-of-scope

- Real-WAS integration (Phase 3-A) — replace mocked `urlopen` with real calls
  in a separate integration-tests file.
- Reconnect / backoff — Phase 3-B.
- Auth tokens — Phase 4.

## Linked Docs
- Hub: [_index.md](_index.md)
- Overview: [overview.md](overview.md)
- Bugs: [bugs.md](bugs.md)
