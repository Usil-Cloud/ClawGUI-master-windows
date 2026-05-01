# ClawGUI-Agent Project Map

Top-level index of features and their docs. See [docs/CONVENTIONS.md](docs/CONVENTIONS.md) for the doc-tree rules.

## Phase 1 — Local Windows Execution Layer

**Current focus (2026-05-01):** Phase 1-F live tests on the desktop (RTX 5070 Ti).
Driver loop = laptop sends natural-language commands → desktop executes via
Phase 1-E connection manager → Phase 1-F perception adapter verifies outcome.
Phase 1-F multi-tier (2B + 7B) install + hot-swap wrapper landed on `main`.

| ID  | Feature                       | Source                                       | Primary Doc                                                         | Status   |
|-----|-------------------------------|----------------------------------------------|---------------------------------------------------------------------|----------|
| 1-A | Windows Screenshot            | `phone_agent/windows/screenshot.py`          | _pending_                                                           | active   |
| 1-B | Core GUI Actions              | `phone_agent/windows/device.py`              | _pending_                                                           | active   |
| 1-B | App Resolver (helper for 1-B) | `phone_agent/windows/app_resolver.py`        | _pending_                                                           | active   |
| 1-C | Keyboard Input                | `phone_agent/windows/input.py`               | _pending_                                                           | active   |
| 1-D | Window Manager                | `phone_agent/windows/window_manager.py`      | [docs/features/window_manager/_index.md](docs/features/window_manager/_index.md) | active   |
| 1-E | **Connection Manager**        | `phone_agent/windows/connection.py`          | [docs/features/connection_manager/_index.md](docs/features/connection_manager/_index.md) | **ready for laptop→PC live tests** |
| 1-F | **GUI-Owl Perception Adapter** | `phone_agent/perception/gui_owl_adapter.py` | [docs/features/gui_owl_perception/_index.md](docs/features/gui_owl_perception/_index.md) | **ready for desktop live tests (multi-tier 2B+7B installer + hot-swap on `main`)** |
| 1-G | Step-Independent Memory       | `phone_agent/memory/step_memory.py`          | _pending_                                                           | not started |
| 1-H | **MCP Server (5 top-level tools)** | `phone_agent/windows/mcp_server.py` + `mcp_handlers/` | [docs/features/mcp_server/_index.md](docs/features/mcp_server/_index.md) | active — skeleton |

## Cross-cutting integration tests

| Suite | Source | Primary Doc | Status |
|-------|--------|-------------|--------|
| Multi-App Integration (1-C + 1-D) | `tests/windows/test_multi_app_integration.py` | [docs/features/multi_app_integration/_index.md](docs/features/multi_app_integration/_index.md) | active |
| Phase 1 end-of-phase smoke         | `tests/integration/cross_feature/test_phase1_smoke.py` _(pending)_ | [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md) | not started |

## Integration contract

Public dataclasses and HTTP wire formats that cross feature boundaries are
tracked in [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md). Update
it in the same PR as any shape change.

## Reusable blocks

Shared modules used by more than one feature live in
[docs/REUSABLE_BLOCKS.md](docs/REUSABLE_BLOCKS.md). Consult before writing any
new utility; update when adding a new shared module or a new consumer of an
existing one.

## Cross-cutting

| Module           | Source                                     | Primary Doc                                     | Status |
|------------------|--------------------------------------------|-------------------------------------------------|--------|
| Test Safety Layer | `phone_agent/windows/safety.py`           | _pending_                                       | active |
| App Registry (PID-scoped, cross-run) | `phone_agent/windows/app_registry.py` | [docs/features/multi_app_integration/app_registry.md](docs/features/multi_app_integration/app_registry.md) | active |

## Tests

All Windows test docs live under [docs/tests/windows/_index.md](docs/tests/windows/_index.md).
