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

## bug-4
- **Title:** `run_gui_owl.py` requires manual venv activation; `ModuleNotFoundError: torch` if launched from any other Python
- **Symptom:** Running `python scripts/dev/run_gui_owl.py --default-tier=2b` from the project shell fails at `import torch` because torch is only installed in the perception venv at `~/.clawgui/venv-perception/`.
- **Cause:** The wrapper assumed the user activated the perception venv first. Activation is fragile on Windows (requires PowerShell execution policy adjustment, easy to forget, easy to do in a different terminal than where you run the command).
- **Fix:** Added `_ensure_perception_venv()` to `run_gui_owl.py`: if `import torch` fails, the script finds `~/.clawgui/venv-perception/Scripts/python.exe` and re-execs itself under that interpreter via `subprocess.run`. Also stripped the manual activation step from `test_machine_setup.md` §3 and added a PowerShell execution policy note.
- **Status:** fixed
- **File:** `scripts/dev/run_gui_owl.py`, `docs/features/gui_owl_perception/test_machine_setup.md`

## bug-5
- **Title:** `bitsandbytes` 0.44.1 has no CUDA 12.8 binary; int4 quantization fails with `AttributeError: function 'cquantize_blockwise_fp16_fp4' not found`
- **Symptom:** Wrapper crashes on first model load with `AttributeError: function 'cquantize_blockwise_fp16_fp4' not found` deep inside `bnb.nn.Params4bit.to(target_device)`. Earlier in the install, bnb prints `Could not find the bitsandbytes CUDA binary at .../libbitsandbytes_cuda128.dll. The installed version of bitsandbytes was compiled without GPU support.`
- **Cause:** `bitsandbytes==0.44.1` (released mid-2024) ships pre-compiled CUDA DLLs only up through `cuda125`. Our `torch==2.11.0+cu128` wheel was built for **CUDA 12.8**, so bnb can't locate a matching DLL, falls back to a CPU-only stub, and that stub is missing the `cquantize_blockwise_fp16_fp4` symbol that the int4 quantizer calls. The smoke test in `setup_perception_env.py` did not catch this because it loads the model in plain fp16 with no `load_in_4bit=True`, bypassing the bnb path entirely. The wrapper (`run_gui_owl.py:_load_tier`) DOES use `load_in_4bit=True`, so it hits the bug on first call.
- **Fix:** Bumped `bitsandbytes==0.44.1` → `bitsandbytes==0.49.2` in `requirements_perception.txt` (0.49.x ships `libbitsandbytes_cuda128.dll`). Also fixed a parallel deprecated-kwarg bug in `run_gui_owl.py:_load_tier` (`torch_dtype=` → `dtype=`).
- **Followup:** The smoke test should mirror the wrapper's load path (use `load_in_4bit=True`) so future bnb/CUDA mismatches are caught at install time, not first-request time. Tracked separately.
- **Status:** fixed
- **File:** `requirements_perception.txt`, `scripts/dev/run_gui_owl.py`

<!-- Template for future entries:

## bug-1
- **Title:** ...
- **Symptom:** ...
- **Cause:** ...
- **Fix:** ...
- **Status:** open | fixed
- **Linked commit:** <sha>

-->
