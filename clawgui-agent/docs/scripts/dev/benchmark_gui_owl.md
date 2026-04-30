---
mirrors: scripts/dev/benchmark_gui_owl.py
last_updated: 2026-04-27
status: active
---

# benchmark_gui_owl

## Purpose
End-to-end live test for 1-F per Q5-A. Captures the VS Code battery, runs
each screenshot through the live `GUIOwlAdapter` (pointed at a running
`run_gui_owl_2b.py` server), measures latency, and writes a markdown report
to `docs/features/gui_owl_perception/benchmarks/<date>_vscode_<runtime>.md`.

## Approach
- Requires a wrapper server already running on `--endpoint` (default
  `http://127.0.0.1:8002`). Fails fast if `/health` doesn't answer.
- Calls `capture_vscode_battery` to produce the 5 screenshots.
- For each: `adapter.analyze(screenshot, prompt=...)`, time it, record
  result + latency.
- Acceptance criteria per Q4-B: 5/5 must return a non-fallback ScreenState
  with at least one element AND non-empty `planned_action`; median latency
  under 30 sec. Records pass/fail per criterion at the bottom of the
  report.
- Markdown report includes per-screenshot: thumbnail path, latency,
  element count, top-3 labels with confidences, planned_action,
  pass/fail.
- Always writes the report — even on failure — so we have an artifact to
  diagnose from.

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Parent: [docs/features/gui_owl_perception/_index.md](../../features/gui_owl_perception/_index.md)
- Wrapper server: [run_gui_owl_2b](run_gui_owl_2b.md)
- Capture script: [capture_vscode_battery](capture_vscode_battery.md)
- Reports land in `docs/features/gui_owl_perception/benchmarks/`
