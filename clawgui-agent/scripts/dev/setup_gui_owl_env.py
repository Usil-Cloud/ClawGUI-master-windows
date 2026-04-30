"""Idempotent installer for the GUI-Owl perception runtime (Phase 1-F).

Targets a fresh Windows test machine with an NVIDIA GPU (>=6 GB VRAM).
Creates an isolated venv at %USERPROFILE%/.clawgui/venv-perception/ so the
multi-GB inference stack never pollutes the project's main env. Re-runnable
safely; each step skips if already done.

Companion doc: docs/scripts/dev/setup_gui_owl_env.md
Setup guide:   docs/features/gui_owl_perception/test_machine_setup.md

Usage
-----
    python scripts/dev/setup_gui_owl_env.py             # full install
    python scripts/dev/setup_gui_owl_env.py --reset     # nuke venv+weights, reinstall
    python scripts/dev/setup_gui_owl_env.py --skip-weights   # deps only
    python scripts/dev/setup_gui_owl_env.py --skip-smoke     # deps + weights, no smoke test
"""
# Notes: docs/scripts/dev/setup_gui_owl_env.md
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
MODEL_REPO_ID = "mPLUG/GUI-Owl-1.5-2B-Instruct"
MODEL_LOCAL_DIR = MODELS_DIR / "GUI-Owl-1.5-2B-Instruct"

PY_MIN = (3, 11)


def _log(msg: str) -> None:
    print(f"[setup] {msg}", flush=True)


def _err(msg: str) -> None:
    print(f"[setup ERROR] {msg}", file=sys.stderr, flush=True)


def _venv_python() -> pathlib.Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(cmd: list[str], **kwargs) -> int:
    _log("$ " + " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, **kwargs)


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


def step_reset() -> None:
    if VENV_DIR.exists():
        _log(f"removing venv: {VENV_DIR}")
        shutil.rmtree(VENV_DIR)
    if MODEL_LOCAL_DIR.exists():
        _log(f"removing model cache: {MODEL_LOCAL_DIR}")
        shutil.rmtree(MODEL_LOCAL_DIR)


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
    _run([py, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
    rc = _run([py, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
    if rc != 0:
        _err("dep install failed — see pip output above")
        sys.exit(1)
    _log("deps installed")


def step_download_weights() -> None:
    if MODEL_LOCAL_DIR.exists() and any(MODEL_LOCAL_DIR.iterdir()):
        _log(f"weights already present at {MODEL_LOCAL_DIR} (skipping)")
        return
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    py = str(_venv_python())
    snippet = textwrap.dedent(f"""
        from huggingface_hub import snapshot_download
        path = snapshot_download(
            repo_id={MODEL_REPO_ID!r},
            local_dir={str(MODEL_LOCAL_DIR)!r},
            local_dir_use_symlinks=False,
        )
        print('downloaded to:', path)
    """)
    rc = _run([py, "-c", snippet])
    if rc != 0:
        _err("weight download failed — check HF auth / network")
        sys.exit(1)
    _log(f"weights at {MODEL_LOCAL_DIR}")


def step_smoke_test() -> None:
    py = str(_venv_python())
    snippet = textwrap.dedent(f"""
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        from PIL import Image

        print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available())
        if not torch.cuda.is_available():
            raise SystemExit('CUDA not available inside the venv — install path is broken')

        path = {str(MODEL_LOCAL_DIR)!r}
        proc = AutoProcessor.from_pretrained(path, trust_remote_code=True)
        model = AutoModelForImageTextToText.from_pretrained(
            path, torch_dtype=torch.float16, device_map='auto', trust_remote_code=True,
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
    rc = _run([py, "-c", snippet])
    if rc != 0:
        _err("smoke test failed — see traceback above")
        sys.exit(1)
    _log("smoke test passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="GUI-Owl perception env installer")
    parser.add_argument("--reset", action="store_true",
                        help="Delete venv + weights cache before installing")
    parser.add_argument("--skip-weights", action="store_true",
                        help="Install deps only, don't download weights")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="Install deps and weights but skip the model-load smoke test")
    args = parser.parse_args()

    _log(f"project root: {PROJECT_ROOT}")
    _log(f"clawgui dir:  {CLAWGUI_DIR}")
    _log(f"venv dir:     {VENV_DIR}")
    _log(f"models dir:   {MODELS_DIR}")

    step_check_python()
    step_check_nvidia()

    if args.reset:
        step_reset()

    step_make_venv()
    step_install_deps()

    if args.skip_weights:
        _log("--skip-weights set; done.")
        return

    step_download_weights()

    if args.skip_smoke:
        _log("--skip-smoke set; done.")
        return

    step_smoke_test()

    _log("")
    _log("=" * 60)
    _log("setup complete. next steps:")
    _log("=" * 60)
    _log("  1. Start the wrapper server:")
    if platform.system() == "Windows":
        _log(f"     {VENV_DIR}\\Scripts\\activate")
    else:
        _log(f"     source {VENV_DIR}/bin/activate")
    _log("     python scripts/dev/run_gui_owl_2b.py --runtime=transformers --port=8002")
    _log("")
    _log("  2. In a SECOND terminal (project venv, not perception venv):")
    _log("     python scripts/dev/benchmark_gui_owl.py --endpoint http://127.0.0.1:8002")
    _log("")


if __name__ == "__main__":
    main()
