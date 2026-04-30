"""Pytest wiring for the perception test suite.

Stubs the heavyweight modules eagerly imported by phone_agent.__init__
(openai, the model client, the agent classes) so unit tests for 1-F don't
require the full inference stack to be installed. Mirrors the pattern used
in tests/windows/conftest.py.
"""
# Notes: docs/tests/perception/conftest.md
from __future__ import annotations

import sys
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


_stub_if_missing("openai",  OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model",         ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent",         PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios",     IOSPhoneAgent=MagicMock)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: opt-in tests that require a real GUI-Owl backend (set CLAWGUI_GUIOWL_LIVE=1)",
    )
    config.addinivalue_line(
        "markers",
        "integration: tests that spin up a real local HTTP server (mock GUI-Owl)",
    )
