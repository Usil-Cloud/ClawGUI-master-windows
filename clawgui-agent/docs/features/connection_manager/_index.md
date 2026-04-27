---
name: Phase 1-E Connection Manager hub
description: Parent doc for Feature 1-E — local vs remote connection split.
type: project
last_updated: 2026-04-26
status: active
---

# Feature 1-E — Connection Manager

**Phase 1, ID 1-E.** Source: `phone_agent/windows/connection.py`. Phase role:
detect at startup whether the agent runs on the same machine as the target
(local mode, direct library calls) or talks to a remote Windows Agent Server
over HTTP (remote mode). The split is transparent to callers.

## Children

| Doc | Purpose |
|-----|---------|
| [overview.md](overview.md) | What the feature does, public API, scope |
| [design.md](design.md) | Dataclass shape, mode-detection rules, urllib choice, legacy coexistence |
| [bugs.md](bugs.md) | Bug tracker (anchors per bug) |

## Source files

- `phone_agent/windows/connection.py` — implementation · doc: [docs/phone_agent/windows/connection.md](../../phone_agent/windows/connection.md)
- `tests/windows/test_connection.py` — unit tests · doc: [docs/tests/windows/test_connection.md](../../tests/windows/test_connection.md)

## Status

| Item | Status |
|------|--------|
| `ConnectionProfile` dataclass | ✅ stable |
| `detect_mode` | ✅ stable |
| `verify_connection` (bool, GET /api/info) | ✅ stable (mock-only — real WAS is Phase 3-A) |
| `get_connection` | ✅ stable |
| `forward_action` | ✅ stable (mock-only) |
| Unit tests | ✅ 17/17 passing |
| Real-WAS integration | ⏳ deferred to Phase 3-A |

## Definition of Done (from roadmap)

- [x] `detect_mode(None)` and `detect_mode('local')` both return `ConnectionProfile(mode='local')`
- [x] `detect_mode('192.168.1.5:7860')` returns `ConnectionProfile(host='192.168.1.5', port=7860, mode='remote')`
- [x] `verify_connection` raises no exception for a healthy WAS; returns `False` (not exception) for unreachable host
- [x] `forward_action` correctly POSTs to `/api/action/click` and returns the WAS response dict

**1-E is feature-complete pending real-WAS validation in Phase 3-A.**

## Open work / next steps

- Phase 3-A: stand up the WAS server and run `verify_connection` /
  `forward_action` against it for end-to-end coverage.

## Related

- Parent roadmap: `Project Ready Player/ClawGUI_Phase1_Roadmap.docx` (Phase 1)
- Sibling features: 1-A Screenshot, 1-B Device Actions, 1-C Keyboard Input, 1-D Window Manager
- Downstream consumer: 1-H Public API + DeviceFactory (selects local vs remote based on profile)
