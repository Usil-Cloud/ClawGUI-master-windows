"""Diagnostic: report the GUI-Owl tier this machine would auto-pick.

Runs the same `_detect_tier_from_vram()` logic the adapter uses, plus prints
the underlying nvidia-smi probe result and the endpoint URL that would be
resolved for the chosen tier (including any env-var overrides).

Usage:
    python scripts/dev/check_gui_owl_tier.py
"""
# Notes: docs/scripts/dev/check_gui_owl_tier.md
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

# Make the project importable when this script is run directly from a
# checkout (no install). Walks up to the clawgui-agent root.
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Stub heavy imports the same way tests/perception/conftest.py does, so this
# script doesn't require the inference stack to be installed.
import types
from unittest.mock import MagicMock


def _stub_if_missing(name: str, **attrs) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except (ImportError, Exception):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod


_stub_if_missing("openai", OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model",         ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent",         PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios",     IOSPhoneAgent=MagicMock)

from phone_agent.config.endpoints import resolve_gui_owl_endpoint  # noqa: E402
from phone_agent.perception.gui_owl_adapter import _detect_tier_from_vram  # noqa: E402


def _raw_nvidia_smi() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5.0, check=True,
        )
        return True, result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
        return False, f"{type(e).__name__}: {e}"


def main() -> None:
    print("=" * 60)
    print("GUI-Owl tier auto-detect — machine diagnostic")
    print("=" * 60)

    ok, raw = _raw_nvidia_smi()
    if ok:
        print(f"\nnvidia-smi: AVAILABLE")
        print(f"  raw output:")
        for line in raw.splitlines():
            print(f"    {line}")
    else:
        from phone_agent.perception.gui_owl_adapter import _DEFAULT_TIER_ON_DETECT_FAIL
        print(f"\nnvidia-smi: NOT AVAILABLE — {raw}")
        print(f"  (adapter will fall back to default tier {_DEFAULT_TIER_ON_DETECT_FAIL!r})")

    tier = _detect_tier_from_vram()
    print(f"\nDetected tier: {tier!r}")

    env_key = f"CLAWGUI_GUIOWL_{tier.upper()}_URL"
    override = os.environ.get(env_key)
    print(f"Env override ({env_key}): "
          f"{override!r}" if override else f"Env override ({env_key}): not set")

    try:
        url = resolve_gui_owl_endpoint(tier)
        print(f"Resolved endpoint: {url}")
    except KeyError as e:
        print(f"Endpoint resolution FAILED: {e}")

    print("\nThis is the configuration the GUIOwlAdapter would pick on this")
    print("machine if you constructed it with model_tier='auto'.")


if __name__ == "__main__":
    main()
