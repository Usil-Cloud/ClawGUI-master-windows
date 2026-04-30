---
mirrors: scripts/dev/check_gui_owl_tier.py
last_updated: 2026-04-27
status: active
---

# check_gui_owl_tier

## Purpose
Runs `phone_agent.perception.gui_owl_adapter._detect_tier_from_vram()` and
reports what tier it would pick on the current machine, plus the underlying
free-VRAM numbers and `nvidia-smi` availability. Useful as a one-line
diagnostic when onboarding a new machine into the deployment matrix
(personas P1 / P2 / P3 from the deployment topologies discussion).

## Approach
- Calls the same private function the adapter uses — keeps detection logic
  in exactly one place.
- Prints: detected tier, free-VRAM bands per GPU (or "no NVIDIA GPU detected"
  fallback path), the env-var override that would be used for that tier, and
  the resolved endpoint URL.
- Exit code 0 always — this is informational, not a gate.

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Adapter: [docs/phone_agent/perception/gui_owl_adapter.md](../../phone_agent/perception/gui_owl_adapter.md)
- Endpoint config: [docs/phone_agent/config/endpoints.md](../../phone_agent/config/endpoints.md)
- Sibling: [mock_gui_owl_server](mock_gui_owl_server.md)
