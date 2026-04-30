---
name: ClawGUI Reusable Blocks Index
description: One-line registry of shared modules that cross feature boundaries. Consult before writing any new utility.
type: reference
last_updated: 2026-04-27
status: active
---

# Reusable Blocks

Shared modules used by more than one feature. **Consult this before writing any
new utility function.** If a block matches what you're about to write, import
it instead. If you write a new shared utility, add a row here in the same PR.

This is the *implementation* registry — `INTEGRATION_CONTRACT.md` is the
*public dataclass / wire-format* registry. Together they're the answer to
"if I touch X, what else cares?"

## How to use this index (workflow)

1. **Before writing a new utility:** grep this file for the verb you're about
   to implement (`open`, `close`, `find`, `capture`, `resolve`, `register`).
   Match found → import. No match → write it; if it'll likely be reused, add a
   row.
2. **Before adding a feature:** scan the "Reuse when…" column for anything that
   could short-circuit your design.
3. **In the spec interview:** when starting a new feature, surface the rows
   that look relevant to what's being built so the user can confirm or
   redirect.
4. **After a bug fix in a shared block:** mention in the commit / PR body
   which downstream consumers benefit (or might regress). Re-run those
   features' tests before declaring done — the end-of-phase smoke test catches
   what individual fixes miss.

## The index

| Block | Source | What it does | Reuse when… | Consumed by |
|---|---|---|---|---|
| `app_resolver` | `phone_agent/windows/app_resolver.py` | Open / close / find Windows apps by name. Handles user-app vs system-app force-close semantics. | You need to launch or terminate any Windows process by app name (notepad, calc, chrome, etc.). | 1-B `device.py`, 1-D `window_manager.py`, 1-C tests, 1-D tests |
| `app_registry` | `phone_agent/windows/app_registry.py` | PID-scoped, cross-run process tracker. Keeps a record of what the agent spawned so we don't double-launch or orphan procs. | You're launching a process and want to know if it's already running, or you want clean teardown across test runs. | 1-B, 1-D, multi-app integration |
| `safety` | `phone_agent/windows/safety.py` | Kill switch (Shift+Right) + presence monitor (mouse/kbd activity detection) for integration tests. `safety_session()` context manager. | Any test that controls real input/windows. | All Windows integration tests |
| `connection` (1-E) | `phone_agent/windows/connection.py` | Local vs remote routing. `is_local()`, `post()`, `ConnectionProfile`. | Any module that needs to call out to the agent server *or* go in-process based on deployment mode. | 1-A `screenshot.py`, future 1-H DeviceFactory |
| `Screenshot` dataclass (1-A) | `phone_agent/windows/screenshot.py` | Captured-image dataclass: base64 PNG + dims + capture mode. Plus `capture()` entry point. | You produce or consume a screenshot anywhere in the pipeline. | 1-F adapter, future 1-G agent loop |
| `ScreenState` / `UIElement` (1-F) | `phone_agent/perception/types.py` | Public perception dataclasses (frozen). Output shape of any VLM-based screen analyzer. | You need a model-agnostic representation of "what's on the screen right now." | 1-F `gui_owl_adapter.py`, future 1-G agent loop |
| `endpoints` (1-F) | `phone_agent/config/endpoints.py` | External inference endpoint registry + env-var override resolver. Currently GUI-Owl /analyze. | You're adding a new external HTTP service that should be tier- or env-configurable. | 1-F adapter; pattern for future model integrations |
| `timing` config | `phone_agent/config/timing.py` | Tunable timing constants (action delays, connection timeouts, device polls). | You need a sleep / timeout that's not test-specific — put it here, not as a literal. | 1-B, 1-D, others |
| `perception venv` (out-of-tree) | `%USERPROFILE%/.clawgui/venv-perception/` (created by `scripts/dev/setup_gui_owl_env.py`) | Isolated Python venv holding the multi-GB inference stack (torch CUDA, transformers, bitsandbytes, GUI-Owl weights). | You're adding a new heavy ML dep that shouldn't be in the project's main env. Use the same out-of-tree pattern, don't bloat `requirements.txt`. | 1-F live wrapper (`scripts/dev/run_gui_owl_2b.py`); future heavy-inference work |
| Heavy-import stub helper | `_stub_if_missing()` (copied across `tests/perception/conftest.py`, `tests/windows/conftest.py`, and the dev scripts) | Replace optional heavyweight modules (`openai`, `phone_agent.model.client`, etc.) with `MagicMock` shims so tests / scripts don't need the full inference stack. | You're writing a script or test that touches `phone_agent` but shouldn't pull the AI/model deps. | All perception + windows tests, all `scripts/dev/*` scripts |

## Recently fixed in shared blocks (downstream regression watch)

When a shared block changes, list affected consumers here so the next end-of-phase
smoke test can verify them. Clear the list after the smoke test passes.

| Date | Block | Change | Re-verify in smoke test |
|---|---|---|---|
| 2026-04-25 | `app_resolver` + `app_registry` | Multi-app duplicate-spawn fix; user-app force-close semantics (commit 8383803) | 1-B `test_device.py`, 1-C `test_input.py`, 1-D `test_window_manager.py` (1-D already verified) |
| 2026-04-30 | All Phase 1 capability modules (1-A → 1-G) | Now consumed via 1-H MCP handlers (`mcp_handlers/*.py`) instead of a custom controller. Any signature change in `screenshot`, `device`, `input`, `window_manager`, `app_resolver`, `app_registry`, `safety`, `gui_owl_adapter`, or `step_memory` must re-verify the matching MCP handler. | All `mcp_handlers/*` once implemented; 1-H smoke test |

## What does NOT belong here

- Single-feature internals (helpers used only by one source file)
- Public dataclasses crossing feature boundaries → those go in `INTEGRATION_CONTRACT.md` instead
- Test-only fixtures → those live in the relevant `conftest.py`

## When the index is wrong

If you find this index missing a shared block, or claiming a consumer
relationship that no longer exists, fix it inline and bump `last_updated`. The
index decays without active maintenance — flag stale rows over deleting them
silently.
