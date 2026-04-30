---
name: ClawGUI Integration Contract
description: Source-of-truth list of public dataclasses + which features produce/consume them. Updated each phase.
type: reference
last_updated: 2026-04-27
status: active
---

# Integration Contract

As Phase 1 features start to compose (perception consumes screenshots, agent loop
consumes perception, etc.), this doc tracks the **public dataclasses and HTTP
contracts** that cross feature boundaries. If you change a shape listed here, you
are touching every consumer — update the table and the cross-feature smoke test
in the same PR.

Smoke-test cadence: **end of each phase milestone** (per integration interview Q3).

## 1. Public dataclasses

| Dataclass | Defined in | Produced by | Consumed by |
|-----------|-----------|-------------|-------------|
| `Screenshot` | `phone_agent/windows/screenshot.py` | 1-A Screenshot | 1-F Perception, 1-G Agent loop |
| `WindowInfo` | `phone_agent/windows/window_manager.py` | 1-D Window Manager | 1-G Agent loop, smoke tests |
| `ConnectionProfile` | `phone_agent/windows/connection.py` | 1-E Connection Manager | 1-H DeviceFactory |
| `ScreenState` | `phone_agent/perception/types.py` | 1-F GUI-Owl Adapter | 1-G Agent loop, 1-H `inspect_screen` + `build_with_claw` |
| `UIElement` | `phone_agent/perception/types.py` | 1-F GUI-Owl Adapter | 1-G Agent loop, 1-H `inspect_screen` |

## 2. HTTP contract — GUI-Owl `/analyze` endpoint (1-F)

Adapter-side contract. The same shape is used by the mock server in unit tests
and by any real GUI-Owl backend (local inference server or hosted API).

### Request
```
POST {endpoint_url}/analyze
Content-Type: multipart/form-data

Fields:
  image:  PNG bytes (the screenshot)
  prompt: str — task context / instruction (optional, may be empty)
  tier:   str — informational, one of '2b' | '7b' | '72b' | '235b'
```

### Response (200)
```json
{
  "elements": [
    {
      "label": "text input field",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.92,
      "type": "input"
    }
  ],
  "planned_action": "click the text input field",
  "reflection": "the screenshot shows an empty notepad window",
  "raw": { "...": "model-specific debug payload" }
}
```

### Error / fallback semantics

If any step fails (connect, request, HTTP non-200, JSON parse, schema mismatch),
the adapter returns a `ScreenState` with:

- `elements = []`
- `planned_action = ""`
- `reflection = ""`
- `raw_response = {"fallback": True, "failed_step": "<step>", "error": "<msg>"}`

`failed_step` ∈ `{"resolve_endpoint", "connect", "http_status", "parse_json",
"parse_schema"}`. Consumers detect fallback via `raw_response["fallback"] is True`.

## 3. Cross-feature smoke tests

Live in `tests/integration/cross_feature/`. Each phase milestone adds one test
that exercises **all features completed up to that phase**.

| Phase milestone | Smoke test | Scope |
|-----------------|------------|-------|
| End of Phase 1 | `tests/integration/cross_feature/test_phase1_smoke.py` | 1-A → 1-H end-to-end. **Must include:** retroactive re-run of 1-B (`test_device.py`) and 1-C (`test_input.py`) to verify they benefit from (not regress on) the 2026-04-25 `app_resolver` / `app_registry` fixes. See `REUSABLE_BLOCKS.md` "Recently fixed" table for the full re-verify list. |

Smoke tests are gated on real OS state (real Notepad window, real screenshot)
and run via the safety layer (`phone_agent/windows/safety.py`).
