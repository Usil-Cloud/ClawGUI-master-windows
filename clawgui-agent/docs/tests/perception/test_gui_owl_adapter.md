---
mirrors: tests/perception/test_gui_owl_adapter.py
last_updated: 2026-04-27
status: active
---

# test_gui_owl_adapter

## Purpose
Unit and opt-in live integration tests for the 1-F GUI-Owl Perception Adapter.

## Approach
- **Mocked endpoint tests:** monkeypatch `requests.post` with a canned Notepad
  fixture response. Assert `analyze()` returns a `ScreenState` with at least
  one `UIElement` whose label contains `'text'` or `'input'` (Task 41 DoD).
- **Fallback tests:** patch `requests.post` to raise; assert the returned
  `ScreenState` has `raw_response['fallback'] is True` and
  `raw_response['failed_step']` is one of the documented stages.
- **Tier-detect tests:** patch the `nvidia-smi` subprocess call to return
  scripted free-VRAM strings; assert each tier band picks the right tier.
- **Endpoint-resolution tests:** verify env-var override beats dict default,
  and unknown tier raises through to the `resolve_endpoint` fallback step.
- **Live test:** `@pytest.mark.live` and skipped unless `CLAWGUI_GUIOWL_LIVE=1`.
  Posts a real Notepad screenshot (captured via 1-A) to whatever endpoint is
  configured.

## Status
- Mocked + fallback + tier-detect + endpoint-resolution: passing
- Live: skipped by default

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Implementation: [docs/phone_agent/perception/gui_owl_adapter.md](../../phone_agent/perception/gui_owl_adapter.md)
