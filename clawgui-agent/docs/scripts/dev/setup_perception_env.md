---
mirrors: scripts/dev/setup_perception_env.py
last_updated: 2026-05-03
status: active
---

# setup_perception_env

## Purpose
Idempotent installer for the GUI-Owl perception runtime on a clean test
machine. Creates an isolated venv, installs pinned deps, downloads one or
more GUI-Owl tiers (2B + 7B by default), runs a smoke test per tier.
Re-runnable safely; each step skips if already done.

Replaces the older `setup_gui_owl_env.py` (which still exists as a thin
deprecation shim that forwards to this script with `--tiers=2b`).

## Approach
- Detects machine (Windows + NVIDIA GPU is the targeted P1/P2 path).
- Creates venv at `%USERPROFILE%\.clawgui\venv-perception\` (out-of-tree —
  won't pollute the project's main env or git status).
- Installs from `requirements_perception.txt` — pinned versions only.
- PyTorch CUDA wheels via `--extra-index-url https://download.pytorch.org/whl/cu128`
  (CUDA 12.8 — required for Blackwell sm_120 / RTX 50xx; older cu121 wheels
  fail on the test machine).
- `TIER_REPOS` maps `'2b' -> mPLUG/GUI-Owl-1.5-2B-Instruct` and
  `'7b' -> mPLUG/GUI-Owl-7B`. Each requested tier is downloaded into
  `%USERPROFILE%\.clawgui\models\<repo-leaf>\` via
  `huggingface_hub.snapshot_download`.
- Smoke test per tier: load model + processor, run one inference on a
  synthetic 256x256 image, confirm output isn't empty.
- `--tiers 2b,7b` (default): installs both. `--tiers 2b` or `--tiers 7b`
  for one only.
- `--reset` deletes the venv + the selected tiers' weight caches.
- `--skip-weights` is for re-running just the dep install when iterating
  on the wrapper.

## Why both tiers by default
The desktop test machine (RTX 5060 Ti, 16 GB VRAM, Blackwell sm_120) can
host either tier individually but not both concurrently. Downloading both at install time
means the wrapper can hot-swap between them at request time without ever
hitting the network again. The installer is the only place that knows
about HuggingFace; runtime stays offline.

## Status
Active — multi-tier path is new and gets validated on the first live
benchmark run on the desktop. The 2B path is unchanged from the previous
`setup_gui_owl_env.py`; the 7B path is exercised for the first time as
part of Phase 1-F live tests.

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Setup guide: [docs/features/gui_owl_perception/test_machine_setup.md](../../features/gui_owl_perception/test_machine_setup.md)
- Pinned deps: `requirements_perception.txt`
- Sibling: [run_gui_owl](run_gui_owl.md)
- Deprecated alias: `scripts/dev/setup_gui_owl_env.py` (forwarder)
