"""Pytest wiring for the Windows test-safety layer.

Every Windows integration test session gets:

  - a 3-2-1 countdown banner before the first test runs,
  - a global ``Shift+Right`` (override via ``CLAWGUI_KILL_HOTKEY``) hotkey
    that aborts the whole run, kills spawned processes, and restores cursor
    + modifier-key state,
  - per-test presence detection: if the user touches mouse or keyboard while
    a test is running, the next test pauses up to 5 seconds for idle and
    then either resumes or aborts.

Set ``CLAWGUI_TEST_SAFETY=0`` to bypass all of this (CI environments).
"""
from __future__ import annotations

import platform
import subprocess
import sys
import time
import types
from unittest.mock import MagicMock

import pytest

# Shared Notepad proc — started once at session scope, consumed by all test
# classes that need a live Notepad window (window_manager, input, screenshot,
# multi_app_integration).  Using a mutable list so test-file module-level code
# can reference the same object and pick up the proc after it is populated.
_shared_notepad: list = [None]  # [subprocess.Popen | None]


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


_stub_if_missing("openai",  OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("requests", get=MagicMock, post=MagicMock, RequestException=Exception)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model",         ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent",         PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios",     IOSPhoneAgent=MagicMock)

# Import safety directly without going through phone_agent.windows.__init__
# (which pulls in heavyweight Win32-only modules we don't need for the safety layer).
import importlib  # noqa: E402
safety = importlib.import_module("phone_agent.windows.safety")


# ── session-wide kill switch + countdown ─────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _safety_session():
    with safety.safety_session() as state:
        yield state


# ── session-wide shared Notepad ──────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _shared_notepad_session(_safety_session):  # noqa: F811
    """Open one Notepad for the entire test session; register it with safety."""
    if platform.system() != "Windows":
        yield
        return
    try:
        import win32gui
    except ImportError:
        yield
        return

    proc = subprocess.Popen(["notepad.exe"])
    safety.register_process(proc)
    _shared_notepad[0] = proc

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        found: list[int] = []
        def _cb(h, _):
            if win32gui.IsWindowVisible(h) and "Notepad" in win32gui.GetWindowText(h):
                found.append(h)
        win32gui.EnumWindows(_cb, None)
        if found:
            break
        time.sleep(0.1)

    yield proc

    _shared_notepad[0] = None
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=3)


# ── per-test presence monitor ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _presence_monitor(request):
    if not safety.ENABLED:
        yield
        return
    pm = safety.PresenceMonitor()
    # If the previous test detected user input, pause/abort BEFORE this one starts.
    try:
        pm.wait_for_idle_or_abort()
    except safety.UserInterferenceAbort as exc:
        pytest.exit(f"safety abort: {exc}", returncode=130)
    pm.mark_test_start()
    safety.STATE.current_step = request.node.nodeid
    yield
    safety.STATE.current_step = ""
