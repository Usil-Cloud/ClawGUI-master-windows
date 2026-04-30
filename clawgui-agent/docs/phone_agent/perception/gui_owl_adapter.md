---
mirrors: phone_agent/perception/gui_owl_adapter.py
last_updated: 2026-04-27
status: active
---

# gui_owl_adapter

## Purpose
Wraps a GUI-Owl (Mobile-Agent v3) inference endpoint. Sends a `Screenshot` over
HTTP, parses the response into a `ScreenState`. The **only** GUI-Owl-aware file
in the project — every other module uses `ScreenState` / `UIElement` and stays
model-agnostic.

## Approach
- `GUIOwlAdapter(model_tier='auto', endpoint_url=None, prompt_default='', request_timeout=30.0)`
- Tier auto-detection runs `nvidia-smi` once at construct time; result is cached
  on the instance.
- `analyze(screenshot, prompt='')` does multipart POST to `{endpoint}/analyze`
  with `image` (PNG bytes) + `prompt` + `tier`. Each pipeline stage is wrapped
  with a named `failed_step` for the fallback path.
- Fallback returns a `ScreenState` whose `raw_response` includes
  `{"fallback": True, "failed_step": ..., "error": ...}` and logs WARNING.
- HTTP done via `requests` (already in `requirements.txt`).

## Status
- Construct + tier resolution: stable
- `analyze()` mocked-endpoint path: stable + tested
- `analyze()` live-endpoint path: works, gated on `CLAWGUI_GUIOWL_LIVE=1`
- Fallback contract: stable + tested

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Sibling types: [docs/phone_agent/perception/types.md](types.md)
- Endpoint config: [docs/phone_agent/config/endpoints.md](../config/endpoints.md)
- Tests: [docs/tests/perception/test_gui_owl_adapter.md](../../tests/perception/test_gui_owl_adapter.md)
- Wire contract: [docs/INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md)
