---
mirrors: phone_agent/config/endpoints.py
last_updated: 2026-04-27
status: active
---

# endpoints

## Purpose
Central registry of external inference endpoints. For Phase 1-F, that's the
GUI-Owl `/analyze` endpoint per model tier. Switching tiers in production is
a config change here (or an env-var override) — never a code change in the
adapter or downstream modules.

## Approach
- `GUI_OWL_ENDPOINTS: dict[str, str]` — defaults pointing at localhost on
  per-tier ports (placeholder until a real backend exists).
- `resolve_gui_owl_endpoint(tier: str) -> str` checks env vars first, falls
  back to the dict. Env-var names: `CLAWGUI_GUIOWL_2B_URL`, `..._7B_URL`,
  `..._72B_URL`, `..._235B_URL`.
- Raises `KeyError` if `tier` isn't one of the four known tiers (the adapter
  catches this and returns a fallback `ScreenState` with
  `failed_step='resolve_endpoint'`).

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Consumer: [docs/phone_agent/perception/gui_owl_adapter.md](../perception/gui_owl_adapter.md)
