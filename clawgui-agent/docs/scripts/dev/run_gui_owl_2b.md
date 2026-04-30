---
mirrors: scripts/dev/run_gui_owl_2b.py
last_updated: 2026-04-27
status: active
---

# run_gui_owl_2b

## Purpose
HTTP wrapper that exposes GUI-Owl-1.5-2B-Instruct on the `/analyze` wire
contract documented in `INTEGRATION_CONTRACT.md`. Two interchangeable
runtimes per Q2-B: in-process `transformers` (tested), or relay to a remote
`vLLM` OpenAI-compatible endpoint (unverified — code is written but not
exercised until someone has a vLLM server to point at).

## Approach
- `--runtime=transformers` (default): loads
  `mPLUG/GUI-Owl-1.5-2B-Instruct` once at startup via
  `transformers.Qwen3VLForConditionalGeneration` + `AutoProcessor`. Uses
  `bitsandbytes` int4 on CUDA, fp16 on CPU. Subsequent /analyze requests
  reuse the loaded model.
- `--runtime=vllm`: forwards to a remote vLLM `v1/chat/completions`
  endpoint specified by `--base-url`. Uses the `openai` Python SDK as the
  client.
- Both runtimes prompt the model for a JSON response shaped like our
  `/analyze` schema (elements, planned_action, reflection). Best-effort
  parser: if the model returns text-with-JSON-block, extract; if it returns
  free-form text, dump it into `planned_action` and return empty elements.
- Same multipart upload contract as the mock server. `/health` returns 200.

## Status
- transformers runtime: implementation complete; tested on a clean install
  per `test_machine_setup.md`.
- vLLM runtime: implementation complete; **unverified** — needs a real
  vLLM server to validate.

## Known Bugs
None.

## Linked Docs
- Wire contract: [docs/INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md)
- Adapter (consumer): [docs/phone_agent/perception/gui_owl_adapter.md](../../phone_agent/perception/gui_owl_adapter.md)
- Setup: [setup_gui_owl_env](setup_gui_owl_env.md)
- Mock equivalent: [mock_gui_owl_server](mock_gui_owl_server.md)
