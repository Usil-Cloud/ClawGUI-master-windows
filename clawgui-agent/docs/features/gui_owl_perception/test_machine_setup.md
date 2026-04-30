---
mirrors: docs/features/gui_owl_perception/
last_updated: 2026-04-27
status: active
---

# Test Machine Setup — Phase 1-F Live Validation

Step-by-step clean-install procedure for running the live GUI-Owl benchmark
on a Windows test machine with an NVIDIA GPU (≥6 GB VRAM). Re-runnable from
scratch — every step is idempotent or has an explicit reset path.

## 0. Prerequisites (verify, don't install)

| Requirement | Check command | What to do if missing |
|---|---|---|
| Windows 10/11 | `ver` | n/a — we target Windows |
| Python 3.11+ | `python --version` | Install from python.org, add to PATH |
| Git | `git --version` | Install Git for Windows |
| NVIDIA GPU + driver | `nvidia-smi` | Install latest NVIDIA Game Ready / Studio driver |
| CUDA toolkit (12.x) | `nvcc --version` | Optional for runtime; PyTorch wheels bundle CUDA. Skip if you only have driver. |
| VS Code | `code --version` | Install from code.visualstudio.com — needed for benchmark |
| Hugging Face account | log in via `huggingface-cli login` | Create at huggingface.co; the GUI-Owl model is public, but rate limits are friendlier when authed |

## 1. Get the project

```powershell
git clone <repo-url> C:\clawgui-agent
cd C:\clawgui-agent
git checkout windows-management-module   # or whichever branch
```

## 2. Run the setup script

```powershell
python scripts\dev\setup_gui_owl_env.py
```

What it does:

1. Creates an isolated venv at `%USERPROFILE%\.clawgui\venv-perception\`
   (out-of-tree — doesn't pollute the project's main env or git status).
2. Installs pinned deps from `requirements_perception.txt` — including
   PyTorch with CUDA 12.1 wheels, transformers, bitsandbytes, qwen-vl-utils.
3. Downloads `mPLUG/GUI-Owl-1.5-2B-Instruct` to
   `%USERPROFILE%\.clawgui\models\GUI-Owl-1.5-2B-Instruct\` (~5 GB
   safetensors; bitsandbytes int4-quantizes at load time, not at download).
4. Smoke test: loads the model, runs one inference on a synthetic image,
   confirms output isn't empty.
5. Prints a summary with the commands for the next steps.

**Expected wall time:** 10–20 min depending on download speed.

**To force a fully clean re-run:**

```powershell
python scripts\dev\setup_gui_owl_env.py --reset
```

This deletes the venv and weights cache before reinstalling.

**To re-run dep install only** (e.g., after a wrapper code change):

```powershell
python scripts\dev\setup_gui_owl_env.py --skip-weights
```

## 3. Start the wrapper server

In one terminal:

```powershell
%USERPROFILE%\.clawgui\venv-perception\Scripts\activate
python scripts\dev\run_gui_owl_2b.py --runtime=transformers --port=8002
```

Wait for `gui-owl wrapper listening on http://127.0.0.1:8002/analyze (Ctrl+C to stop)`.
First request triggers a 30–60 sec model load.

## 4. Run the benchmark

In a second terminal (project venv, **not** the perception venv — the
benchmark uses 1-A screenshot which lives in the main env):

```powershell
python scripts\dev\benchmark_gui_owl.py --endpoint http://127.0.0.1:8002
```

What it does:

1. Confirms the wrapper server is alive (GET `/health`).
2. Captures the 5 VS Code reference screenshots via
   `capture_vscode_battery` (real VS Code launch + state changes).
3. Runs each through `GUIOwlAdapter`, measures latency.
4. Writes a report to
   `docs\features\gui_owl_perception\benchmarks\<date>_vscode_transformers.md`.

**Expected wall time:** 2–5 min (5 inferences × <1 sec on GPU + capture
overhead).

**Acceptance criteria per Q4-B:** 5/5 screenshots must return non-fallback
ScreenState with at least one element AND non-empty `planned_action`;
median latency under 30 sec.

## 5. Stop everything

In the wrapper terminal: `Ctrl+C`.

To free disk later:

```powershell
python scripts\dev\setup_gui_owl_env.py --reset
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `nvidia-smi` not found in setup | Driver not installed | Install NVIDIA driver; reboot |
| `Could not load library cudnn_*` | PyTorch CUDA mismatch with driver | Driver too old — update; or pin a different torch CUDA version in `requirements_perception.txt` |
| `OOM` at model load | <6 GB free VRAM | Close other GPU apps; or set `--runtime=transformers --device=cpu` in the wrapper (much slower) |
| Wrapper server returns fallback `connect` for every request | Wrapper crashed silently | Check the wrapper terminal for traceback; common cause is bitsandbytes/CUDA mismatch |
| Benchmark complains "VS Code not found" | `code` not on PATH | Add `C:\Users\<you>\AppData\Local\Programs\Microsoft VS Code\bin` to PATH |
| Tests already running on this branch fail after setup | Perception venv leaked into project env | `setup_gui_owl_env.py` writes to `%USERPROFILE%\.clawgui\venv-perception\` only; ensure you didn't activate it for the project venv |

## Files this setup creates / touches

| Path | Purpose | Removed by `--reset` |
|---|---|---|
| `%USERPROFILE%\.clawgui\venv-perception\` | Isolated Python venv | ✅ |
| `%USERPROFILE%\.clawgui\models\GUI-Owl-1.5-2B-Instruct\` | Model weights | ✅ |
| `docs\features\gui_owl_perception\benchmarks\fixtures\<timestamp>\*.png` | Captured screenshots | ❌ (kept for reference) |
| `docs\features\gui_owl_perception\benchmarks\<date>_vscode_*.md` | Benchmark reports | ❌ |

Nothing is written under the project tree's source directories. `git status`
should be clean of artifacts after a setup run (only the new benchmark
report and fixture screenshots will appear).
