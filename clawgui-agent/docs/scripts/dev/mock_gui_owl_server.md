---
mirrors: scripts/dev/mock_gui_owl_server.py
last_updated: 2026-04-27
status: active
---

# mock_gui_owl_server

## Purpose
Stdlib HTTP server that speaks the GUI-Owl `/analyze` wire contract documented
in `docs/INTEGRATION_CONTRACT.md`. Lets the 1-F adapter be exercised over a
real network round-trip (multipart upload, real socket I/O, real JSON
parsing) without standing up an actual GUI-Owl model. Used by both the
`MockServerIntegrationTests` class and as a standalone foreground script for
manual smoke testing.

## Approach
- `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` — zero deps.
- `POST /analyze` parses multipart, returns a configurable canned JSON
  response (default: the Notepad fixture from the unit tests).
- `GET /health` returns `{"ok": true}`.
- `--port 0` picks a free port (pytest fixture uses this).
- `--response-file <path>` lets tests inject a malformed payload (used by the
  malformed-bbox regression test from Q4).
- `start_server_in_thread(...)` is the programmatic entry point used by
  pytest; the `if __name__ == "__main__"` block is the CLI path.

## Status
Stable.

## Known Bugs
None.

## Linked Docs
- Wire contract: [docs/INTEGRATION_CONTRACT.md](../../INTEGRATION_CONTRACT.md)
- Consumer (tests): [docs/tests/perception/test_gui_owl_adapter.md](../../tests/perception/test_gui_owl_adapter.md)
- Sibling: [check_gui_owl_tier](check_gui_owl_tier.md)
