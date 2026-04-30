---
name: scripts/dev/ index
description: Development utilities — mock servers, diagnostics, one-off probes.
type: reference
last_updated: 2026-04-30
status: active
---

# scripts/dev/

Local-only development utilities. Not part of the runtime, not shipped to
users. Reach for these when you need to validate something end-to-end without
standing up the full stack.

- [mock_gui_owl_server](mock_gui_owl_server.md) — Stdlib HTTP server that mimics the GUI-Owl `/analyze` wire format · status: active
- [check_gui_owl_tier](check_gui_owl_tier.md) — Diagnostic: report what tier `_detect_tier_from_vram()` picks on this machine · status: active
- [setup_perception_env](setup_perception_env.md) — Multi-tier installer for the GUI-Owl runtime (2B + 7B by default) · status: active
- [run_gui_owl](run_gui_owl.md) — HTTP wrapper exposing any installed GUI-Owl tier on `/analyze`; hot-swaps tiers on demand · status: active
- [capture_vscode_battery](capture_vscode_battery.md) — Captures the 5-screenshot VS Code reference battery for benchmarking · status: active
- [benchmark_gui_owl](benchmark_gui_owl.md) — End-to-end live benchmark; writes markdown report · status: active

Deprecated forwarders (kept temporarily so old runbooks don't break):
- `scripts/dev/setup_gui_owl_env.py` — forwards to `setup_perception_env.py --tiers=2b`
- `scripts/dev/run_gui_owl_2b.py` — forwards to `run_gui_owl.py --default-tier=2b --pin`
