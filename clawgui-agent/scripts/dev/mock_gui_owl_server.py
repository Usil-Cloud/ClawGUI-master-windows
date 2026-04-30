"""Mock GUI-Owl /analyze server.

Speaks the wire contract from docs/INTEGRATION_CONTRACT.md without standing
up the actual model. Used by MockServerIntegrationTests and as a standalone
script for manual smoke testing.

CLI:
    python scripts/dev/mock_gui_owl_server.py --port 8002

Programmatic (used by tests):
    server, port = start_server_in_thread()
    try:
        ...                       # adapter targets http://127.0.0.1:{port}
    finally:
        stop_server(server)
"""
# Notes: docs/scripts/dev/mock_gui_owl_server.md
from __future__ import annotations

import argparse
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_NOTEPAD_RESPONSE: dict[str, Any] = {
    "elements": [
        {"label": "text input area", "bbox": [10, 50, 800, 600],
         "confidence": 0.97, "type": "input"},
        {"label": "File menu", "bbox": [0, 0, 40, 20],
         "confidence": 0.91, "type": "button"},
    ],
    "planned_action": "click the text input area and type 'hello'",
    "reflection": "screenshot shows an empty Notepad window",
    "raw": {"model": "mock", "latency_ms": 0},
}

MALFORMED_BBOX_RESPONSE: dict[str, Any] = {
    "elements": [
        {"label": "broken element", "bbox": [10, 50, 800],
         "confidence": 0.5, "type": "other"},
    ],
    "planned_action": "n/a",
    "reflection": "n/a",
    "raw": {"model": "mock", "scenario": "malformed_bbox_3_ints"},
}


def _make_handler(response_payload: dict[str, Any]):
    class _Handler(BaseHTTPRequestHandler):

        def log_message(self, format: str, *args: Any) -> None:
            log.debug("mock-gui-owl: " + format, *args)

        def do_GET(self) -> None:
            if self.path == "/health":
                body = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/analyze":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            # Drain the request body — we don't actually need to parse the
            # multipart, just confirm one was sent. Real GUI-Owl backends will
            # parse it; the adapter's job is to send it correctly.
            _ = self.rfile.read(length) if length else b""
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"):
                self.send_error(400, f"expected multipart, got {ctype!r}")
                return
            body = json.dumps(response_payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def start_server_in_thread(
    port: int = 0, response: dict[str, Any] | None = None
) -> tuple[ThreadingHTTPServer, int]:
    handler = _make_handler(response if response is not None else DEFAULT_NOTEPAD_RESPONSE)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port


def stop_server(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock GUI-Owl /analyze server")
    parser.add_argument("--port", type=int, default=8002,
                        help="Port to bind (0 = pick a free port)")
    parser.add_argument("--response-file", type=str, default=None,
                        help="Optional JSON file to use as the canned /analyze response")
    parser.add_argument("--malformed-bbox", action="store_true",
                        help="Serve a deliberately malformed payload (3-int bbox) — for fallback tests")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.malformed_bbox:
        payload = MALFORMED_BBOX_RESPONSE
    elif args.response_file:
        with open(args.response_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = DEFAULT_NOTEPAD_RESPONSE

    server, port = start_server_in_thread(args.port, payload)
    print(f"mock-gui-owl listening on http://127.0.0.1:{port}/analyze (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        stop_server(server)


if __name__ == "__main__":
    main()
