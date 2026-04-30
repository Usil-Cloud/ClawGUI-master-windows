---
mirrors: scripts/dev/capture_vscode_battery.py
last_updated: 2026-04-27
status: active
---

# capture_vscode_battery

## Purpose
Captures the 5-screenshot VS Code reference battery used by the perception
benchmark (Q3-A): empty new window, welcome page, file tree expanded with a
Python project, code in editor + terminal open, command palette open.

## Approach
- Launches VS Code via `code` (or the resolved `Code.exe` path). Reuses
  `phone_agent.windows.app_resolver` per `REUSABLE_BLOCKS.md`.
- Drives state changes via real keyboard input (1-C `input.py`) — opens
  command palette with `Ctrl+Shift+P`, opens terminal with `` Ctrl+` ``,
  expands the explorer, etc.
- Uses 1-A `get_screenshot()` for capture; saves PNGs to
  `docs/features/gui_owl_perception/benchmarks/fixtures/<timestamp>/`.
- Each screenshot has a sibling `.label.txt` describing the expected
  visible regions (used by the benchmark's eyeball check).
- Wraps everything in the `safety` session (kill switch + presence monitor)
  per the existing test pattern.

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Sibling: [benchmark_gui_owl](benchmark_gui_owl.md)
- Reuses: `app_resolver`, `screenshot`, `input`, `safety`
- Reuse index: [docs/REUSABLE_BLOCKS.md](../../REUSABLE_BLOCKS.md)
