---
mirrors: scripts/dev/setup_gui_owl_env.py
last_updated: 2026-04-27
status: active
---

# setup_gui_owl_env

## Purpose
Idempotent installer for the GUI-Owl perception runtime on a clean test
machine. Creates an isolated venv, installs pinned deps, downloads the
GUI-Owl-1.5-2B-Instruct weights, runs a smoke test. Re-runnable safely;
each step skips if already done.

## Approach
- Detects machine (Windows + NVIDIA GPU is the targeted P1/P2 path).
- Creates venv at `%USERPROFILE%\.clawgui\venv-perception\` (out-of-tree —
  won't pollute the project's main env or git status).
- Installs from `requirements_perception.txt` — pinned versions only.
- PyTorch CUDA wheels via `--index-url https://download.pytorch.org/whl/cu121`.
- Weights cached at `%USERPROFILE%\.clawgui\models\GUI-Owl-1.5-2B-Instruct\`
  via `huggingface_hub.snapshot_download`.
- Smoke test: load model + processor, run one inference on a synthetic
  256×256 image, confirm output isn't empty.
- `--reset` deletes the venv + weights to force a fully clean run.
- `--skip-weights` is for re-running just the dep install when iterating on
  the wrapper.

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Setup guide: [docs/features/gui_owl_perception/test_machine_setup.md](../../features/gui_owl_perception/test_machine_setup.md)
- Pinned deps: `requirements_perception.txt`
- Sibling: [run_gui_owl_2b](run_gui_owl_2b.md)
