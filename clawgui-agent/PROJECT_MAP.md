# ClawGUI-Agent Project Map

Top-level index of features and their docs. See [docs/CONVENTIONS.md](docs/CONVENTIONS.md) for the doc-tree rules.

## Phase 1 — Local Windows Execution Layer

| ID  | Feature                       | Source                                       | Primary Doc                                                         | Status   |
|-----|-------------------------------|----------------------------------------------|---------------------------------------------------------------------|----------|
| 1-A | Windows Screenshot            | `phone_agent/windows/screenshot.py`          | _pending_                                                           | active   |
| 1-B | Core GUI Actions              | `phone_agent/windows/device.py`              | _pending_                                                           | active   |
| 1-B | App Resolver (helper for 1-B) | `phone_agent/windows/app_resolver.py`        | _pending_                                                           | active   |
| 1-C | Keyboard Input                | `phone_agent/windows/input.py`               | _pending_                                                           | active   |
| 1-D | Window Manager                | `phone_agent/windows/window_manager.py`      | [docs/features/window_manager/_index.md](docs/features/window_manager/_index.md) | active   |
| 1-E | **Connection Manager**        | `phone_agent/windows/connection.py`          | [docs/features/connection_manager/_index.md](docs/features/connection_manager/_index.md) | **active — current focus** |
| 1-F | GUI-Owl Perception Adapter    | `phone_agent/perception/gui_owl_adapter.py`  | _pending_                                                           | not started |
| 1-G | Step-Independent Memory       | `phone_agent/memory/step_memory.py`          | _pending_                                                           | not started |
| 1-H | Public API + DeviceFactory    | `phone_agent/windows/__init__.py` + factory  | _pending_                                                           | not started |

## Cross-cutting integration tests

| Suite | Source | Primary Doc | Status |
|-------|--------|-------------|--------|
| Multi-App Integration (1-C + 1-D) | `tests/windows/test_multi_app_integration.py` | [docs/features/multi_app_integration/_index.md](docs/features/multi_app_integration/_index.md) | active |

## Cross-cutting

| Module           | Source                                     | Primary Doc                                     | Status |
|------------------|--------------------------------------------|-------------------------------------------------|--------|
| Test Safety Layer | `phone_agent/windows/safety.py`           | _pending_                                       | active |
| App Registry (PID-scoped, cross-run) | `phone_agent/windows/app_registry.py` | [docs/features/multi_app_integration/app_registry.md](docs/features/multi_app_integration/app_registry.md) | active |

## Tests

All Windows test docs live under [docs/tests/windows/_index.md](docs/tests/windows/_index.md).
