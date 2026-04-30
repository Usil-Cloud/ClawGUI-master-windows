---
name: Phase 1-F GUI-Owl Perception Adapter hub
description: Parent doc for Feature 1-F — wraps GUI-Owl (Mobile-Agent v3) and normalizes output to ScreenState.
type: project
last_updated: 2026-04-30
status: active
---

# Feature 1-F — GUI-Owl Perception Adapter

**Phase 1, ID 1-F.** Source: `phone_agent/perception/gui_owl_adapter.py`. Phase
role: take a `Screenshot` from 1-A, send it to a GUI-Owl inference endpoint,
and return a normalized `ScreenState` for the agent loop to consume. This is
the **only** GUI-Owl-aware module in the project.

## Children

| Doc | Purpose |
|-----|---------|
| [overview.md](overview.md) | What the feature does, public API, scope |
| [design.md](design.md) | Dataclass shape, tier detection, fallback contract, wire format |
| [bugs.md](bugs.md) | Bug tracker (anchors per bug) |

## Source files

- `phone_agent/perception/types.py` — `ScreenState`, `UIElement` dataclasses · doc: [docs/phone_agent/perception/types.md](../../phone_agent/perception/types.md)
- `phone_agent/perception/gui_owl_adapter.py` — adapter implementation · doc: [docs/phone_agent/perception/gui_owl_adapter.md](../../phone_agent/perception/gui_owl_adapter.md)
- `phone_agent/config/endpoints.py` — per-tier endpoint URL map + env overrides · doc: [docs/phone_agent/config/endpoints.md](../../phone_agent/config/endpoints.md)
- `tests/perception/test_gui_owl_adapter.py` — unit + opt-in live tests · doc: [docs/tests/perception/test_gui_owl_adapter.md](../../tests/perception/test_gui_owl_adapter.md)

## Status

| Item | Status |
|------|--------|
| `ScreenState` / `UIElement` dataclasses | ✅ stable |
| `GUIOwlAdapter` constructor + tier resolution | ✅ stable |
| `analyze()` — mocked endpoint path | ✅ stable |
| `analyze()` — live endpoint path | ⏳ deferred (no real GUI-Owl backend yet) |
| Fallback mode (named failed_step) | ✅ stable |
| VRAM-based tier auto-detect | ✅ stable (nvidia-smi subprocess) |
| Unit tests | ✅ passing (mocked endpoint + fallback + tier-detect) |
| Live integration test | ⏳ gated on `CLAWGUI_GUIOWL_LIVE=1` |

## Definition of Done (from roadmap)

- [x] `analyze()` returns a `ScreenState` with at least one `UIElement` from a Notepad screenshot (mocked fixture; live test gated)
- [x] `planned_action` field contains a non-empty string in the success path
- [x] Fallback activates cleanly when GUI-Owl is unavailable — agent loop continues, `raw_response['fallback'] is True`
- [x] Model tier selection picks endpoint from config; switching tiers is a config change only
- [x] Adapter is the only file importing GUI-Owl; `device.py`, `agent.py`, `server.py` stay clean

## Tested environments

| Date | Machine | nvidia-smi | Detected tier | Notes |
|---|---|---|---|---|
| 2026-04-27 | Luis's laptop (Win11) | not available | `'2b'` (fallback default) | Non-NVIDIA setup. The `'2b'` fallback default is correct here per the 2026-04-30 resolution. |
| _pending_ | Luis's desktop (Win11, RTX 5070 Ti, 16 GB) | available | `'7b'` (24 GB threshold not crossed → bucket = 7b) | Phase 1-F live tests. Both 2B and 7B installed via `setup_perception_env.py`; hot-swap wrapper validated end-to-end. |

## Resolved design questions

- **Non-NVIDIA fallback default (resolved 2026-04-30).** `_DEFAULT_TIER_ON_DETECT_FAIL = '2b'`
  is correct: when `nvidia-smi` is missing we assume "no discrete NVIDIA GPU"
  (P3 persona) and `'2b'` is the realistic pick. Stale `design.md` updated
  to match the code; no code change.

## Open work / next steps

- Run the live benchmark on the desktop (RTX 5070 Ti) for both 2B and 7B tiers — see [test_machine_setup.md](test_machine_setup.md)
- Phase 1-G will consume `ScreenState` from this adapter

## Related

- Parent roadmap: `Project Ready Player/ClawGUI_Phase1_Roadmap.docx` (Phase 1)
- Upstream producer: 1-A Screenshot (`phone_agent/windows/screenshot.py`)
- Downstream consumer: 1-G Step-Independent Memory + agent loop
- Integration contract: [docs/INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md)
