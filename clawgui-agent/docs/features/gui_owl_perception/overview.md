---
mirrors: docs/features/gui_owl_perception/
last_updated: 2026-04-27
status: active
---

# Overview — 1-F GUI-Owl Perception Adapter

## What it does

Takes a `Screenshot` (from 1-A), sends it to a GUI-Owl (Mobile-Agent v3)
inference endpoint over HTTP, and returns a `ScreenState` containing a list of
detected `UIElement`s, a planned next action, the model's reflection, and the
raw response payload.

## Public API

```python
from phone_agent.perception import GUIOwlAdapter, ScreenState, UIElement

adapter = GUIOwlAdapter(model_tier="auto")   # or "2b" | "7b" | "72b" | "235b"
state: ScreenState = adapter.analyze(screenshot, prompt="open notepad and type hello")
```

- `state.elements` — `list[UIElement]`, may be empty in fallback
- `state.planned_action` — natural-language action string ("" in fallback)
- `state.reflection` — model's reasoning string ("" in fallback)
- `state.raw_response` — full dict from model server, plus `{"fallback": True, "failed_step": ...}` if the call failed

## Scope

- **In scope:** HTTP wire format, response normalization, tier selection,
  fallback contract.
- **Out of scope:** running the GUI-Owl model itself (lives behind the endpoint),
  prompt engineering for specific tasks (caller passes the prompt), action
  execution (1-B handles that).

## Why this is the only GUI-Owl-aware file

Per Phase 1-F DoD: `device.py`, `agent.py`, `server.py` must stay model-agnostic.
Swapping GUI-Owl for a different VLM later is a one-file change. Consumers
import only the dataclasses from `phone_agent/perception/types.py`, which has
no GUI-Owl dependencies.
