---
mirrors: scripts/dev/run_gui_owl.py
last_updated: 2026-04-30
status: active
---

# run_gui_owl

## Purpose
HTTP wrapper that exposes any installed GUI-Owl tier (2B / 7B) on the
`/analyze` wire contract documented in `INTEGRATION_CONTRACT.md`. Hot-swaps
the loaded tier on demand based on the per-request `tier` form field, so a
single port and process can serve multiple tiers from a 16 GB-class GPU
where they don't fit concurrently.

Two interchangeable runtimes per Q2-B: in-process `transformers` (tested),
or relay to a remote `vLLM` OpenAI-compatible endpoint (unverified).

## Approach
- `--runtime=transformers` (default): warms `--default-tier` at startup via
  `AutoModelForImageTextToText` + `AutoProcessor`, with `bitsandbytes`
  int4 on CUDA. Subsequent requests check the per-request `tier` field; if
  it differs from the active tier, the model+processor are deleted, the
  CUDA cache is emptied, and the requested tier is loaded.
- `--pin` disables hot-swap and locks the server to `--default-tier`. Used
  by the `run_gui_owl_2b.py` backwards-compat shim.
- Tier → HF repo mapping is imported from `setup_perception_env.py` so the
  wrapper and installer cannot drift on names or local paths.
- `--runtime=vllm`: forwards to a remote vLLM `v1/chat/completions` endpoint
  specified by `--base-url`. vLLM is single-model, so tier hot-swap is a
  no-op there — the requested tier is reported back in `raw.served_tier`
  but doesn't change the underlying model.
- Both runtimes prompt the model for a JSON response shaped like our
  `/analyze` schema. Best-effort parser: extract a JSON block if present,
  else dump raw text into `planned_action`.
- `/health` returns the active tier and the list of known tiers.

## Status
- transformers runtime, hot-swap: implementation complete; needs live
  validation on the desktop test machine (Phase 1-F live tests).
- vLLM runtime: implementation complete; **unverified** — needs a real
  vLLM server to validate.

## Known Bugs
None.

## Linked Docs
- Wire contract: [docs/INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md)
- Adapter (consumer): [docs/phone_agent/perception/gui_owl_adapter.md](../../phone_agent/perception/gui_owl_adapter.md)
- Setup: [setup_perception_env](setup_perception_env.md)
- Mock equivalent: [mock_gui_owl_server](mock_gui_owl_server.md)
