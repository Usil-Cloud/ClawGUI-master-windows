"""Idempotent installer for the GUI-Owl perception runtime (Phase 1-F).

Targets a fresh Windows test machine with an NVIDIA GPU. Creates an isolated
venv at %USERPROFILE%/.clawgui/venv-perception/ so the multi-GB inference stack
never pollutes the project's main env. Re-runnable safely; each step skips if
already done.

Multi-tier support
------------------
    --tiers 2b           # download just 2B (matches old setup_gui_owl_env.py)
    --tiers 7b           # download just 7B
    --tiers 2b,7b        # default — both tiers, hot-swappable by run_gui_owl.py

VRAM rule of thumb (int4 quantized at load time):
    2B  ~= 1.5 GB resident
    7B  ~= 4.5 GB resident
    Both fit on a 16 GB card individually but not concurrently — use the
    hot-swap wrapper to switch between them at request time.

Companion doc: docs/scripts/dev/setup_perception_env.md
Setup guide:   docs/features/gui_owl_perception/test_machine_setup.md

Usage
-----
    python scripts/dev/setup_perception_env.py                 # both tiers
    python scripts/dev/setup_perception_env.py --tiers 2b      # 2B only
    python scripts/dev/setup_perception_env.py --reset         # nuke everything
    python scripts/dev/setup_perception_env.py --skip-weights  # deps only
    python scripts/dev/setup_perception_env.py --skip-smoke    # deps + weights
"""
# Notes: docs/scripts/dev/setup_perception_env.md
from __future__ import annotations

import argparse
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import textwrap

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements_perception.txt"

CLAWGUI_DIR = pathlib.Path(os.path.expanduser("~")) / ".clawgui"
VENV_DIR = CLAWGUI_DIR / "venv-perception"
MODELS_DIR = CLAWGUI_DIR / "models"

# Single source of truth for tier -> HuggingFace repo. The wrapper server
# (run_gui_owl.py) imports this same map so we cannot drift.
TIER_REPOS: dict[str, str] = {
    "2b": "mPLUG/GUI-Owl-1.5-2B-Instruct",
    "7b": "mPLUG/GUI-Owl-7B",
}

PY_MIN = (3, 11)

ALL_TIERS = tuple(TIER_REPOS)


def _log(msg: str) -> None:
    print(f"[setup] {msg}", flush=True)


def _err(msg: str) -> None:
    print(f"[setup ERROR] {msg}", file=sys.stderr, flush=True)


def _venv_python() -> pathlib.Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _model_dir_for(tier: str) -> pathlib.Path:
    repo_id = TIER_REPOS[tier]
    return MODELS_DIR / repo_id.split("/", 1)[1]


def _has_model_weights(directory: pathlib.Path) -> bool:
    """True only when actual weight files (not just config/tokenizer files) are present."""
    weight_exts = {".safetensors", ".bin", ".pt", ".ckpt"}
    return any(f.suffix in weight_exts for f in directory.rglob("*") if f.is_file())


def _run(cmd: list[str], **kwargs) -> int:
    _log("$ " + " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, **kwargs)


def _parse_tiers(raw: str) -> list[str]:
    tiers = [t.strip().lower() for t in raw.split(",") if t.strip()]
    bad = [t for t in tiers if t not in TIER_REPOS]
    if bad:
        _err(f"unknown tier(s): {bad}; expected subset of {ALL_TIERS}")
        sys.exit(2)
    return tiers


def step_check_python() -> None:
    if sys.version_info < PY_MIN:
        _err(f"Python >= {PY_MIN[0]}.{PY_MIN[1]} required; have {sys.version_info[:2]}")
        sys.exit(1)
    _log(f"Python {sys.version.split()[0]} OK")


def step_check_nvidia() -> None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5.0, check=True,
        )
        for line in result.stdout.strip().splitlines():
            _log(f"GPU: {line.strip()}")
    except (FileNotFoundError, subprocess.SubprocessError):
        _err("nvidia-smi not available — this setup targets NVIDIA + CUDA. "
             "If the test machine has no GPU, run with --runtime=cpu in the "
             "wrapper instead, or change requirements_perception.txt to drop "
             "the +cu121 torch wheels.")
        sys.exit(1)


def step_reset(tiers: list[str]) -> None:
    if VENV_DIR.exists():
        _log(f"removing venv: {VENV_DIR}")
        shutil.rmtree(VENV_DIR)
    for tier in tiers:
        d = _model_dir_for(tier)
        if d.exists():
            _log(f"removing model cache: {d}")
            shutil.rmtree(d)


def step_make_venv() -> None:
    if _venv_python().exists():
        _log(f"venv already exists at {VENV_DIR} (skipping)")
        return
    CLAWGUI_DIR.mkdir(parents=True, exist_ok=True)
    rc = _run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if rc != 0:
        _err("venv creation failed")
        sys.exit(1)
    _log(f"venv created at {VENV_DIR}")


def step_install_deps() -> None:
    py = str(_venv_python())
    _run([py, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools<82"])
    rc = _run([py, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
    if rc != 0:
        _err("dep install failed — see pip output above")
        sys.exit(1)
    _log("deps installed")


def step_download_weights(tier: str) -> None:
    repo_id = TIER_REPOS[tier]
    local_dir = _model_dir_for(tier)
    if local_dir.exists() and _has_model_weights(local_dir):
        _log(f"[{tier}] weights already present at {local_dir} (skipping)")
        return
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    py = str(_venv_python())
    snippet = textwrap.dedent(f"""
        from huggingface_hub import snapshot_download
        path = snapshot_download(
            repo_id={repo_id!r},
            local_dir={str(local_dir)!r},
        )
        print('downloaded to:', path)
    """)
    _log(f"[{tier}] downloading {repo_id} ...")
    rc = _run([py, "-c", snippet])
    if rc != 0:
        _err(f"[{tier}] weight download failed — check HF auth / network")
        sys.exit(1)
    _log(f"[{tier}] weights at {local_dir}")


def step_smoke_test(tier: str) -> None:
    py = str(_venv_python())
    local_dir = _model_dir_for(tier)
    snippet = textwrap.dedent(f"""
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        from PIL import Image

        print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available())
        if not torch.cuda.is_available():
            raise SystemExit('CUDA not available inside the venv — install path is broken')

        path = {str(local_dir)!r}
        proc = AutoProcessor.from_pretrained(path, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            path, dtype=torch.float16, device_map='auto', trust_remote_code=True,
        )
        img = Image.new('RGB', (256, 256), (200, 200, 220))
        msgs = [{{'role': 'user', 'content': [
            {{'type': 'image', 'image': img}},
            {{'type': 'text', 'text': 'Describe what you see in one sentence.'}},
        ]}}]
        text = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        inputs = proc(text=[text], images=[img], return_tensors='pt').to(model.device)
        out = model.generate(**inputs, max_new_tokens=32, do_sample=False)
        decoded = proc.batch_decode(out, skip_special_tokens=True)[0]
        print('SMOKE TEST OUTPUT:', decoded[-200:])
        if not decoded.strip():
            raise SystemExit('empty output — model load looks broken')
    """)
    _log(f"[{tier}] running smoke test ...")
    rc = _run([py, "-c", snippet])
    if rc != 0:
        _err(f"[{tier}] smoke test failed — see traceback above")
        sys.exit(1)
    _log(f"[{tier}] smoke test passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="GUI-Owl perception env installer")
    parser.add_argument(
        "--tiers", type=str, default=",".join(ALL_TIERS),
        help=f"Comma-separated tiers to install. Subset of {ALL_TIERS}. "
             f"Default: all of them.",
    )
    parser.add_argument("--reset", action="store_true",
                        help="Delete venv + selected weight caches before installing")
    parser.add_argument("--skip-weights", action="store_true",
                        help="Install deps only, don't download weights")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="Install deps and weights but skip the model-load smoke test")
    args = parser.parse_args()

    tiers = _parse_tiers(args.tiers)

    _log(f"project root: {PROJECT_ROOT}")
    _log(f"clawgui dir:  {CLAWGUI_DIR}")
    _log(f"venv dir:     {VENV_DIR}")
    _log(f"models dir:   {MODELS_DIR}")
    _log(f"tiers:        {tiers}")

    step_check_python()
    step_check_nvidia()

    if args.reset:
        step_reset(tiers)

    step_make_venv()
    step_install_deps()

    if args.skip_weights:
        _log("--skip-weights set; done.")
        return

    for tier in tiers:
        step_download_weights(tier)

    if args.skip_smoke:
        _log("--skip-smoke set; done.")
        return

    for tier in tiers:
        step_smoke_test(tier)

    _log("")
    _log("=" * 60)
    _log("setup complete. next steps:")
    _log("=" * 60)
    if platform.system() == "Windows":
        activate = f"{VENV_DIR}\\Scripts\\activate"
    else:
        activate = f"source {VENV_DIR}/bin/activate"
    _log(f"  1. Activate the perception venv:")
    _log(f"     {activate}")
    _log("")
    _log(f"  2. Start the wrapper server (hot-swaps between installed tiers):")
    default_tier = tiers[0]
    _log(f"     python scripts/dev/run_gui_owl.py --default-tier={default_tier}")
    _log("")
    _log(f"  3. In a SECOND terminal (project venv, not perception venv):")
    for tier in tiers:
        _log(f"     python scripts/dev/benchmark_gui_owl.py --tier={tier}")
    _log("")


if __name__ == "__main__":
    main()
