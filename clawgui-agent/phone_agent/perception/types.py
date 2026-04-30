"""Public dataclasses for the perception layer.

Defined in their own module so consumers (agent loop, tests) can import the
shapes without pulling in the GUI-Owl adapter or its HTTP/CUDA dependencies.
"""
# Notes: docs/phone_agent/perception/types.md
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UIElement:
    label: str
    bbox: tuple[int, int, int, int]
    confidence: float
    element_type: str


@dataclass(frozen=True)
class ScreenState:
    elements: tuple[UIElement, ...]
    planned_action: str
    reflection: str
    raw_response: dict[str, Any] = field(default_factory=dict)
