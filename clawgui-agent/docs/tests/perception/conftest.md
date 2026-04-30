---
mirrors: tests/perception/conftest.py
last_updated: 2026-04-27
status: active
---

# conftest

## Purpose
Pytest wiring for `tests/perception/`. Stubs the heavyweight modules eagerly
imported by `phone_agent/__init__.py` (`openai`, `phone_agent.model`, the
agent classes) so the 1-F unit tests can run without the full inference stack
installed. Mirrors the pattern used in `tests/windows/conftest.py`.

## Approach
- `_stub_if_missing(name, **attrs)` — only inserts a `MagicMock`-backed stub
  module if the real one fails to import. Real `requests` (which the adapter
  actually uses) is left intact.
- Registers the `live` pytest mark used by the opt-in integration test.

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Sibling: [docs/tests/perception/test_gui_owl_adapter.md](test_gui_owl_adapter.md)
- Pattern source: `tests/windows/conftest.py`
