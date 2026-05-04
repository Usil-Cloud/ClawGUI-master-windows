---
mirrors: docs/features/gui_owl_perception/
last_updated: 2026-05-04
status: active
---

# Bugs — 1-F GUI-Owl Perception Adapter

## bug-1
- **Title:** Incomplete weight download silently skipped; smoke test always fails
- **Symptom:** `OSError: Error no file named pytorch_model.bin, model.safetensors … found in directory … GUI-Owl-1.5-2B-Instruct`. Model dir exists with only JSON config/tokenizer files, no `.safetensors` weights.
- **Cause:** `step_download_weights` skipped re-download because `any(local_dir.iterdir())` returned True (config files exist). The original download was interrupted after the small files (config/tokenizer) but before the large weight blobs transferred.
- **Fix:** Replaced `any(local_dir.iterdir())` with `_has_model_weights()` which only returns True when `.safetensors`/`.bin`/`.pt`/`.ckpt` files are present. Also removed deprecated `local_dir_use_symlinks=False` from `snapshot_download` call.
- **Status:** fixed
- **File:** `scripts/dev/setup_perception_env.py`

## bug-2
- **Title:** `setuptools` upgrade conflict breaks torch install
- **Symptom:** `ERROR: pip's dependency resolver … torch 2.11.0+cu128 requires setuptools<82, but you have setuptools 82.0.1 which is incompatible.`
- **Cause:** `step_install_deps` ran `pip install --upgrade setuptools` with no upper bound, pulling in 82.x.
- **Fix:** Pinned to `setuptools<82` in the upgrade command.
- **Status:** fixed
- **File:** `scripts/dev/setup_perception_env.py`

## bug-3
- **Title:** Deprecated `torch_dtype` kwarg in smoke test
- **Symptom:** `torch_dtype is deprecated! Use dtype instead!` warning during smoke test.
- **Cause:** `AutoModelForImageTextToText.from_pretrained` called with `torch_dtype=` (old API).
- **Fix:** Changed to `dtype=torch.float16`.
- **Status:** fixed
- **File:** `scripts/dev/setup_perception_env.py`

<!-- Template for future entries:

## bug-1
- **Title:** ...
- **Symptom:** ...
- **Cause:** ...
- **Fix:** ...
- **Status:** open | fixed
- **Linked commit:** <sha>

-->
