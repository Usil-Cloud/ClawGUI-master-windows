---
name: scripts/dev/ index
description: Development utilities — mock servers, diagnostics, one-off probes.
type: reference
last_updated: 2026-04-27
status: active
---

# scripts/dev/

Local-only development utilities. Not part of the runtime, not shipped to
users. Reach for these when you need to validate something end-to-end without
standing up the full stack.

- [mock_gui_owl_server](mock_gui_owl_server.md) — Stdlib HTTP server that mimics the GUI-Owl `/analyze` wire format · status: active
- [check_gui_owl_tier](check_gui_owl_tier.md) — Diagnostic: report what tier `_detect_tier_from_vram()` picks on this machine · status: active
- [setup_gui_owl_env](setup_gui_owl_env.md) — Idempotent installer for the GUI-Owl runtime on a clean test machine · status: active
- [run_gui_owl_2b](run_gui_owl_2b.md) — HTTP wrapper exposing GUI-Owl-1.5-2B on the `/analyze` contract (transformers + vLLM runtimes) · status: active
- [capture_vscode_battery](capture_vscode_battery.md) — Captures the 5-screenshot VS Code reference battery for benchmarking · status: active
- [benchmark_gui_owl](benchmark_gui_owl.md) — End-to-end live benchmark; writes markdown report · status: active
