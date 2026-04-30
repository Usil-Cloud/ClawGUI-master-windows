"""External inference endpoint registry.

Per Phase 1-F: GUI-Owl `/analyze` URLs, one per model tier. Switching tiers in
production is a config change here (or an env-var override) — never a code
change in the adapter or its consumers.
"""
# Notes: docs/phone_agent/config/endpoints.md
from __future__ import annotations

import os

GUI_OWL_TIERS: tuple[str, ...] = ("2b", "7b", "72b", "235b")

GUI_OWL_ENDPOINTS: dict[str, str] = {
    "2b":   "http://localhost:8001",
    "7b":   "http://localhost:8002",
    "72b":  "http://localhost:8003",
    "235b": "http://localhost:8004",
}


def resolve_gui_owl_endpoint(tier: str) -> str:
    if tier not in GUI_OWL_TIERS:
        raise KeyError(f"unknown GUI-Owl tier {tier!r}; expected one of {GUI_OWL_TIERS}")
    env_key = f"CLAWGUI_GUIOWL_{tier.upper()}_URL"
    override = os.environ.get(env_key)
    if override:
        return override.rstrip("/")
    return GUI_OWL_ENDPOINTS[tier].rstrip("/")
