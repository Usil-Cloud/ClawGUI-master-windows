---
mirrors: phone_agent/windows/mcp_handlers/run_command.py
last_updated: 2026-04-30
status: active
---

# run_command

## Purpose

Implements `run_command`: shell execution mode of the product. Returns
stdout, stderr, exit code, and optional file captures. The CLI counterpart
to GUI-mode `navigate_windows` / `build_with_claw`.

## Approach

`subprocess.run` with `shell=True` on Windows, configurable `cwd` and
`timeout_s`. Output is captured as text (UTF-8 with replacement). When
`capture_files` is supplied, listed paths are read after exec and returned
base64-encoded so the client sees them inline.

## Status

Stub — returns canned CommandResult.

## Known Bugs

None.

## Linked Docs

- Parent: `docs/features/mcp_server/_index.md`
