---
mirrors: docs/features/gui_owl_perception/
last_updated: 2026-05-03
status: active
---

# Test Machine Setup — Phase 1-F Live Validation

Step-by-step clean-install procedure for running the live GUI-Owl benchmark
on a Windows test machine with an NVIDIA GPU. Re-runnable from scratch —
every step is idempotent or has an explicit reset path.

**Reference target:** RTX 5060 Ti, 16 GB VRAM (Blackwell sm_120). The 2B
and 7B tiers fit individually but not concurrently; the multi-tier wrapper
(`run_gui_owl.py`) hot-swaps between them on demand.

## 0. Prerequisites (verify, don't install)

| Requirement | Check command | What to do if missing |
|---|---|---|
| Windows 10/11 | `ver` | n/a — we target Windows |
| Python 3.11+ | `python --version` | Install from python.org, add to PATH |
| Git | `git --version` | Install Git for Windows |
| NVIDIA GPU + driver | `nvidia-smi` | Install latest NVIDIA Game Ready / Studio driver |
| CUDA toolkit (12.x) | `nvcc --version` | Optional for runtime; PyTorch wheels bundle CUDA. Skip if you only have driver. |
| VS Code | `code --version` | Install from code.visualstudio.com — needed for benchmark |
| Hugging Face account | log in via `huggingface-cli login` | Create at huggingface.co; the GUI-Owl models are public, but rate limits are friendlier when authed |

## 1. Get the project

```powershell
git clone <repo-url> C:\clawgui-agent
cd C:\clawgui-agent
git checkout phase-1f-live-tests   # or whichever branch
```

## 2. Run the setup script

Default — install **both 2B and 7B**:

```powershell
python scripts\dev\setup_perception_env.py
```

To install only one tier:

```powershell
python scripts\dev\setup_perception_env.py --tiers 2b
python scripts\dev\setup_perception_env.py --tiers 7b
```

What it does:

1. Creates an isolated venv at `%USERPROFILE%\.clawgui\venv-perception\`
   (out-of-tree — doesn't pollute the project's main env or git status).
2. Installs pinned deps from `requirements_perception.txt` — including
   PyTorch with CUDA 12.8 wheels (required for Blackwell sm_120; older
   cu121 wheels fail with "no kernel image is available" on RTX 50xx),
   transformers >=4.52 (required for the 2B model's `qwen3_vl`
   architecture), bitsandbytes, qwen-vl-utils.
3. For each requested tier, downloads the HF repo into
   `%USERPROFILE%\.clawgui\models\<repo-leaf>\`:
   - `2b` → `mPLUG/GUI-Owl-1.5-2B-Instruct` (~5 GB)
   - `7b` → `mPLUG/GUI-Owl-7B` (~16 GB BF16; bitsandbytes int4-quantizes
     at load time, not at download)
4. Smoke test per tier: loads the model, runs one inference on a synthetic
   image, confirms output isn't empty.
5. Prints a summary with the commands for the next steps.

**Expected wall time:** 15–35 min for both tiers, dominated by the 7B
download.

**To force a fully clean re-run:**

```powershell
python scripts\dev\setup_perception_env.py --reset
```

This deletes the venv and selected weight caches before reinstalling.

**To re-run dep install only:**

```powershell
python scripts\dev\setup_perception_env.py --skip-weights
```

## 3. Start the wrapper server

In one terminal. PowerShell's default execution policy blocks `Activate.ps1`,
so either bypass for the session first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "$env:USERPROFILE\.clawgui\venv-perception\Scripts\Activate.ps1"
python scripts\dev\run_gui_owl.py --default-tier=2b --port=8002
```

…or skip activation entirely and call the venv's python directly (most
reliable; works regardless of execution policy):

```powershell
& "$env:USERPROFILE\.clawgui\venv-perception\Scripts\python.exe" scripts\dev\run_gui_owl.py --default-tier=2b --port=8002
```

Wait for `gui-owl wrapper listening on http://127.0.0.1:8002/analyze ...`.
The default tier is loaded at startup (~30–60 sec for 2B; ~60–120 sec for
7B). Hot-swap to the other tier happens lazily on the first request that
sets `tier=7b` (or `tier=2b`).

To pin to a single tier (no hot-swap):

```powershell
python scripts\dev\run_gui_owl.py --default-tier=7b --pin --port=8002
```

## 4. Configure adapter endpoints

In the second terminal (project venv, **not** the perception venv), point
both per-tier env vars at the single hot-swap server:

```powershell
$env:CLAWGUI_GUIOWL_2B_URL = "http://127.0.0.1:8002"
$env:CLAWGUI_GUIOWL_7B_URL = "http://127.0.0.1:8002"
```

The adapter sends `tier` as a multipart form field, and the wrapper hot-swaps
based on it. If you instead run two separate processes on different ports,
set the two env vars to those distinct URLs.

## 5. Run the benchmark

Same second terminal. Run once per tier:

```powershell
python scripts\dev\benchmark_gui_owl.py --tier 2b --endpoint http://127.0.0.1:8002
python scripts\dev\benchmark_gui_owl.py --tier 7b --endpoint http://127.0.0.1:8002
```

What each run does:

1. Confirms the wrapper server is alive (GET `/health`).
2. Captures the 5 VS Code reference screenshots via
   `capture_vscode_battery` (real VS Code launch + state changes).
3. Runs each through `GUIOwlAdapter` with the requested tier, measures
   latency.
4. Writes a report to
   `docs\features\gui_owl_perception\benchmarks\<date>_vscode_<tier>_transformers.md`.

The first request after a tier switch pays the load cost (model evict +
reload from local disk) — typically ~30 sec for 2B, ~60 sec for 7B. The
benchmark median latency target (≤30 sec) is per-screenshot, so capture
the second-run-onwards numbers if needed.

**Expected wall time:** ~5 min per tier (first request swap + 5 inferences
+ capture overhead).

**Acceptance criteria per Q4-B:** for each tier, 5/5 screenshots must
return non-fallback ScreenState with at least one element AND non-empty
`planned_action`; median latency under 30 sec.

## 6. Stop everything

In the wrapper terminal: `Ctrl+C`.

To free disk later:

```powershell
python scripts\dev\setup_perception_env.py --reset
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `nvidia-smi` not found in setup | Driver not installed | Install NVIDIA driver; reboot |
| `Could not load library cudnn_*` | PyTorch CUDA mismatch with driver | Driver too old — update; or pin a different torch CUDA version in `requirements_perception.txt` |
| `CUDA error: no kernel image is available for execution` / `sm_120 not compatible` | RTX 50xx (Blackwell) on a torch wheel that pre-dates sm_120 | Confirm `requirements_perception.txt` has `torch>=2.7.0` and `--extra-index-url ...whl/cu128`; re-run setup with `--reset` |
| `KeyError: 'qwen3_vl'` / `model type qwen3_vl ... not recognized` | transformers <4.52 (2B model uses qwen3_vl architecture) | Confirm `requirements_perception.txt` has `transformers>=4.52.0`; re-run setup with `--reset` |
| `Activate.ps1` runs but prompt doesn't change to `(venv-perception)` | PowerShell execution policy silently blocked the script | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the session first, or skip activation and call `& "$env:USERPROFILE\.clawgui\venv-perception\Scripts\python.exe" ...` directly |
| `ModuleNotFoundError: No module named 'torch'` when launching wrapper | Activation didn't take; `python` resolved to system interpreter, not venv | Same as above — verify your prompt shows `(venv-perception)` before running, or call the venv's python directly |
| `OOM` at 7B model load | <6 GB free VRAM after other processes | Close other GPU apps; try `--default-tier=2b` only; or set `--pin` to keep one tier resident and avoid swap-back overhead |
| Wrapper returns fallback `connect` for every request | Wrapper crashed silently | Check the wrapper terminal for traceback; common cause is bitsandbytes/CUDA mismatch |
| Wrapper returns fallback `http_status` 500 with "RuntimeError: server pinned" | You sent `tier=7b` to a `--pin --default-tier=2b` server | Restart wrapper without `--pin`, or restart with `--default-tier=7b` |
| Benchmark complains "VS Code not found" | `code` not on PATH | Add `C:\Users\<you>\AppData\Local\Programs\Microsoft VS Code\bin` to PATH |
| First request after tier switch is slow | Expected — hot-swap evict + reload is ~30–60 sec | Pre-warm the target tier with a one-shot request, then start the benchmark |

## Files this setup creates / touches

| Path | Purpose | Removed by `--reset` |
|---|---|---|
| `%USERPROFILE%\.clawgui\venv-perception\` | Isolated Python venv | ✅ |
| `%USERPROFILE%\.clawgui\models\GUI-Owl-1.5-2B-Instruct\` | 2B weights | ✅ (if 2b in --tiers) |
| `%USERPROFILE%\.clawgui\models\GUI-Owl-7B\` | 7B weights | ✅ (if 7b in --tiers) |
| `docs\features\gui_owl_perception\benchmarks\fixtures\<timestamp>\*.png` | Captured screenshots | ❌ (kept for reference) |
| `docs\features\gui_owl_perception\benchmarks\<date>_vscode_<tier>_*.md` | Benchmark reports | ❌ |

Nothing is written under the project tree's source directories. `git status`
should be clean of artifacts after a setup run (only the new benchmark
report and fixture screenshots will appear).
