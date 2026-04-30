---
mirrors: phone_agent/perception/types.py
last_updated: 2026-04-27
status: active
---

# types

## Purpose
Defines `ScreenState` and `UIElement` — the public dataclasses produced by the
GUI-Owl adapter (1-F) and consumed by the agent loop (1-G). Lives in its own
module so consumers don't have to import the adapter (and its HTTP /
GUI-Owl-specific dependencies) just to reference the types.

## Approach
Both dataclasses are `frozen=True`. `ScreenState.elements` is a tuple, not a
list, so the whole structure is hashable and immutable across an agent step.
No imports beyond `dataclasses` — keeps this module dependency-free.

## Status
Stable. Shapes match the wire contract documented in
[INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md).

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Sibling: [docs/phone_agent/perception/gui_owl_adapter.md](gui_owl_adapter.md)
- Contract: [docs/INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md)
