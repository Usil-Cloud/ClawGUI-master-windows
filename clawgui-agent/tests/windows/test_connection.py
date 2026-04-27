"""Tests for phone_agent/windows/connection.py -- Feature 1-E.

Test structure
--------------
Unit tests (ConnectionUnitTests)
    Cover the Phase 1-E spec API end-to-end with mocked HTTP:
        * detect_mode  — None / 'local' / 'host:port' / 'host'
        * verify_connection — healthy 200, timeout, connection refused
        * get_connection — local short-circuit + remote unreachable raises
        * forward_action — mocked POST returns response dict

No real network is touched. Runs on any OS.

Run:
    python -m pytest tests/windows/test_connection.py -v
"""
# Notes: docs/tests/windows/test_connection.md
from __future__ import annotations

import io
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Stub `requests` so connection.py imports cleanly on machines without it.
if "requests" not in sys.modules:
    _r = types.ModuleType("requests")
    _r.post = lambda *a, **kw: None
    _r.get = lambda *a, **kw: None
    sys.modules["requests"] = _r

from phone_agent.windows import connection as cx  # noqa: E402


def _fake_resp(body: bytes, status: int = 200):
    """Build a context-manager object that mimics urlopen()'s return value."""
    obj = MagicMock()
    obj.status = status
    obj.read.return_value = body
    obj.__enter__.return_value = obj
    obj.__exit__.return_value = False
    return obj


class ConnectionUnitTests(unittest.TestCase):

    # ── detect_mode ──────────────────────────────────────────────────────────

    def test_detect_mode_none_is_local(self):
        p = cx.detect_mode(None)
        self.assertEqual(p.mode, "local")
        self.assertEqual(p.host, "localhost")
        self.assertEqual(p.port, 0)

    def test_detect_mode_literal_local(self):
        p = cx.detect_mode("local")
        self.assertEqual(p.mode, "local")

    def test_detect_mode_empty_string_is_local(self):
        self.assertEqual(cx.detect_mode("").mode, "local")

    def test_detect_mode_host_port_is_remote(self):
        p = cx.detect_mode("192.168.1.5:7860")
        self.assertEqual(p.mode, "remote")
        self.assertEqual(p.host, "192.168.1.5")
        self.assertEqual(p.port, 7860)

    def test_detect_mode_bare_host_uses_default_port(self):
        p = cx.detect_mode("10.0.0.7")
        self.assertEqual(p.mode, "remote")
        self.assertEqual(p.host, "10.0.0.7")
        self.assertEqual(p.port, cx.DEFAULT_REMOTE_PORT)

    def test_detect_mode_strips_http_prefix(self):
        p = cx.detect_mode("http://host.example:9000/")
        self.assertEqual(p.host, "host.example")
        self.assertEqual(p.port, 9000)
        self.assertEqual(p.mode, "remote")

    # ── verify_connection ────────────────────────────────────────────────────

    def test_verify_connection_healthy_returns_true(self):
        body = json.dumps({"machine": "BOX-1", "os": "Windows 11"}).encode()
        with patch.object(cx._urlreq, "urlopen", return_value=_fake_resp(body)):
            self.assertTrue(cx.verify_connection("1.2.3.4", 7860))

    def test_verify_connection_unreachable_returns_false(self):
        from urllib.error import URLError
        with patch.object(cx._urlreq, "urlopen", side_effect=URLError("refused")):
            self.assertFalse(cx.verify_connection("1.2.3.4", 7860))

    def test_verify_connection_timeout_returns_false(self):
        with patch.object(cx._urlreq, "urlopen", side_effect=TimeoutError()):
            self.assertFalse(cx.verify_connection("1.2.3.4", 7860, timeout=1))

    def test_verify_connection_non_200_returns_false(self):
        with patch.object(
            cx._urlreq, "urlopen",
            return_value=_fake_resp(b"err", status=500),
        ):
            self.assertFalse(cx.verify_connection("1.2.3.4", 7860))

    def test_verify_connection_bad_json_returns_false(self):
        with patch.object(
            cx._urlreq, "urlopen",
            return_value=_fake_resp(b"not-json"),
        ):
            self.assertFalse(cx.verify_connection("1.2.3.4", 7860))

    # ── get_connection ───────────────────────────────────────────────────────

    def test_get_connection_local_skips_verify(self):
        # Should not call urlopen at all for local mode.
        with patch.object(cx._urlreq, "urlopen", side_effect=AssertionError):
            p = cx.get_connection(None)
        self.assertEqual(p.mode, "local")

    def test_get_connection_remote_healthy_returns_profile(self):
        body = json.dumps({"machine": "BOX-1"}).encode()
        with patch.object(cx._urlreq, "urlopen", return_value=_fake_resp(body)):
            p = cx.get_connection("192.168.1.5:7860")
        self.assertEqual(p.mode, "remote")
        self.assertEqual(p.host, "192.168.1.5")
        self.assertEqual(p.port, 7860)

    def test_get_connection_remote_unreachable_raises(self):
        from urllib.error import URLError
        with patch.object(cx._urlreq, "urlopen", side_effect=URLError("nope")):
            with self.assertRaises(ConnectionError):
                cx.get_connection("192.168.1.5:7860")

    # ── forward_action ───────────────────────────────────────────────────────

    def test_forward_action_posts_to_action_endpoint(self):
        captured = {}
        body = json.dumps({"ok": True, "x": 100}).encode()

        def _fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["data"] = req.data
            captured["method"] = req.get_method()
            return _fake_resp(body)

        profile = cx.ConnectionProfile(host="1.2.3.4", port=7860, mode="remote")
        with patch.object(cx._urlreq, "urlopen", side_effect=_fake_urlopen):
            result = cx.forward_action(profile, "click", {"x": 100, "y": 200})

        self.assertEqual(result, {"ok": True, "x": 100})
        self.assertEqual(captured["url"], "http://1.2.3.4:7860/api/action/click")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(json.loads(captured["data"]), {"x": 100, "y": 200})

    def test_forward_action_accepts_full_path(self):
        captured = {}

        def _fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _fake_resp(b"{}")

        profile = cx.ConnectionProfile(host="h", port=80, mode="remote")
        with patch.object(cx._urlreq, "urlopen", side_effect=_fake_urlopen):
            cx.forward_action(profile, "/custom/path", {})
        self.assertEqual(captured["url"], "http://h:80/custom/path")

    def test_forward_action_rejects_local_profile(self):
        profile = cx.ConnectionProfile(host="localhost", port=0, mode="local")
        with self.assertRaises(ValueError):
            cx.forward_action(profile, "click", {})


if __name__ == "__main__":
    unittest.main()
