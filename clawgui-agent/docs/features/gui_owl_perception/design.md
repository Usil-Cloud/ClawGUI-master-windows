---
mirrors: docs/features/gui_owl_perception/
last_updated: 2026-04-27
status: active
---

# Design — 1-F GUI-Owl Perception Adapter

## Dataclasses

```python
@dataclass(frozen=True)
class UIElement:
    label: str
    bbox: tuple[int, int, int, int]   # (x1, y1, x2, y2) pixel coords
    confidence: float                  # 0.0 .. 1.0
    element_type: str                  # 'button' | 'input' | 'text' | 'icon' | 'other'

@dataclass(frozen=True)
class ScreenState:
    elements: tuple[UIElement, ...]    # tuple, not list — frozen dataclass
    planned_action: str
    reflection: str
    raw_response: dict
```

Both live in `phone_agent/perception/types.py` so consumers (1-G, tests) can
import them without pulling in the adapter or its dependencies. Frozen so they
can't be mutated mid-flight by an agent step.

## Tier selection

```
model_tier ∈ {'auto', '2b', '7b', '72b', '235b'}
```

When `model_tier='auto'` (the default), the adapter shells out to `nvidia-smi
--query-gpu=memory.free --format=csv,noheader,nounits` once at construction
time, parses the largest free-VRAM value (in MiB), and picks:

| Free VRAM    | Tier  |
|--------------|-------|
| < 8 GB       | `2b`  |
| 8–24 GB      | `7b`  |
| 24–80 GB     | `72b` |
| ≥ 80 GB      | `235b`|

If `nvidia-smi` is missing or fails, the adapter falls back to `'7b'` (the
roadmap default) and logs a WARNING.

The user can override at any time by passing an explicit `model_tier` to the
constructor.

## Endpoint configuration

`phone_agent/config/endpoints.py` exposes:

```python
GUI_OWL_ENDPOINTS = {
    "2b":   "http://localhost:8001",
    "7b":   "http://localhost:8002",
    "72b":  "http://localhost:8003",
    "235b": "http://localhost:8004",
}

def resolve_gui_owl_endpoint(tier: str) -> str: ...
```

Per-tier env-var overrides: `CLAWGUI_GUIOWL_2B_URL`, `..._7B_URL`, `..._72B_URL`,
`..._235B_URL`. Switching tiers in production requires only setting the env var
(or editing this file) — no code changes elsewhere.

## Wire format

See [INTEGRATION_CONTRACT.md §2](../../INTEGRATION_CONTRACT.md#2-http-contract--gui-owl-analyze-endpoint-1-f).

## Fallback contract

The adapter wraps each step in a try/except and tags the failure with a
`failed_step` name:

| `failed_step`     | Cause                                             |
|-------------------|---------------------------------------------------|
| `resolve_endpoint`| Unknown tier or empty URL after env override      |
| `connect`         | Network error, refused, DNS fail                  |
| `http_status`     | Non-200 response                                  |
| `parse_json`      | Response body wasn't valid JSON                   |
| `parse_schema`    | JSON missing required fields (`elements`, etc.)   |

Returned `ScreenState` in fallback:
- `elements = ()`
- `planned_action = ""`
- `reflection = ""`
- `raw_response = {"fallback": True, "failed_step": "<name>", "error": "<msg>"}`

A WARNING-level log message names the failed step verbatim so the user can see
which stage of the pipeline broke.

## Why HTTP and not in-process

GUI-Owl checkpoints (especially 72b/235b) are large and have heavy CUDA
dependencies. Keeping inference behind an HTTP boundary lets the adapter run on
a thin client (the agent loop), and lets the model run on a beefy server, on
another machine entirely, or behind a managed API. The wire format is the
contract — what runs behind it is swappable.
