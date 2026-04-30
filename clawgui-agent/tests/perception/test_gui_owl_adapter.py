"""Tests for phone_agent/perception/gui_owl_adapter.py -- Feature 1-F.

Test structure
--------------
- Endpoint resolution (env-var override + unknown-tier KeyError)
- Tier auto-detect (mocked nvidia-smi outputs across all VRAM bands)
- analyze() success path (mocked /analyze response with Notepad fixture)
- analyze() fallback paths (one per documented failed_step)
- Live integration test, gated on CLAWGUI_GUIOWL_LIVE=1, otherwise skipped
"""
# Notes: docs/tests/perception/test_gui_owl_adapter.md
from __future__ import annotations

import base64
import os
import subprocess
import unittest
from unittest.mock import patch, MagicMock

import pytest
import requests

from phone_agent.config.endpoints import resolve_gui_owl_endpoint
from phone_agent.perception import GUIOwlAdapter, ScreenState, UIElement
from phone_agent.perception import gui_owl_adapter as adapter_mod
from phone_agent.windows.screenshot import Screenshot


def _fake_screenshot() -> Screenshot:
    # 1x1 transparent PNG -- shape doesn't matter for unit tests, the wire
    # format is already validated by Pillow/PIL on the server side.
    one_px_png = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB"
        b"9TYS8uYAAAAASUVORK5CYII="
    )
    return Screenshot(
        base64_data=base64.b64encode(one_px_png).decode("ascii"),
        width=1, height=1, mode="full",
    )


NOTEPAD_FIXTURE_RESPONSE = {
    "elements": [
        {"label": "text input area", "bbox": [10, 50, 800, 600],
         "confidence": 0.97, "type": "input"},
        {"label": "File menu",       "bbox": [0, 0, 40, 20],
         "confidence": 0.91, "type": "button"},
    ],
    "planned_action": "click the text input area and type 'hello'",
    "reflection": "screenshot shows an empty Notepad window",
    "raw": {"model": "gui-owl-7b", "latency_ms": 312},
}


def _mock_response(json_payload, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_payload
    m.text = "" if json_payload is not None else "<no body>"
    return m


# ------------------------------------------------------------------
# Endpoint resolution
# ------------------------------------------------------------------
class EndpointResolutionTests(unittest.TestCase):

    def test_default_returns_dict_value(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAWGUI_GUIOWL_7B_URL", None)
            url = resolve_gui_owl_endpoint("7b")
        self.assertTrue(url.startswith("http"))

    def test_env_override_wins(self):
        with patch.dict(os.environ, {"CLAWGUI_GUIOWL_7B_URL": "http://gpu-rig:9999/"}):
            self.assertEqual(resolve_gui_owl_endpoint("7b"), "http://gpu-rig:9999")

    def test_unknown_tier_raises(self):
        with self.assertRaises(KeyError):
            resolve_gui_owl_endpoint("13b")


# ------------------------------------------------------------------
# Tier auto-detect
# ------------------------------------------------------------------
class TierAutoDetectTests(unittest.TestCase):

    def _patch_nvidia_smi(self, stdout: str):
        result = MagicMock(stdout=stdout)
        return patch.object(adapter_mod.subprocess, "run", return_value=result)

    def test_under_8gb_picks_2b(self):
        with self._patch_nvidia_smi("4096\n"):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "2b")

    def test_8_to_24gb_picks_7b(self):
        with self._patch_nvidia_smi("16384\n"):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "7b")

    def test_24_to_80gb_picks_72b(self):
        with self._patch_nvidia_smi("49152\n"):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "72b")

    def test_over_80gb_picks_235b(self):
        with self._patch_nvidia_smi("131072\n"):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "235b")

    def test_picks_max_across_multiple_gpus(self):
        with self._patch_nvidia_smi("4096\n81920\n"):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "235b")

    def test_nvidia_smi_missing_falls_back_to_2b(self):
        # No nvidia-smi -> assume non-NVIDIA / laptop-class hardware (P3).
        with patch.object(
            adapter_mod.subprocess, "run", side_effect=FileNotFoundError()
        ):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "2b")

    def test_unparseable_output_falls_back_to_2b(self):
        with self._patch_nvidia_smi("\n\nweird-text\n"):
            self.assertEqual(adapter_mod._detect_tier_from_vram(), "2b")


# ------------------------------------------------------------------
# analyze() — success path
# ------------------------------------------------------------------
class AnalyzeSuccessTests(unittest.TestCase):

    def setUp(self):
        self.screenshot = _fake_screenshot()
        self.adapter = GUIOwlAdapter(
            model_tier="7b", endpoint_url="http://mock-gui-owl"
        )

    def test_returns_screenstate_with_notepad_elements(self):
        with patch.object(
            adapter_mod.requests, "post",
            return_value=_mock_response(NOTEPAD_FIXTURE_RESPONSE),
        ) as mock_post:
            state = self.adapter.analyze(self.screenshot, prompt="open notepad")

        self.assertIsInstance(state, ScreenState)
        self.assertEqual(len(state.elements), 2)
        for el in state.elements:
            self.assertIsInstance(el, UIElement)
        # Task 41 DoD — at least one element with 'text' or 'input' in label
        labels = [el.label.lower() for el in state.elements]
        self.assertTrue(
            any("text" in lb or "input" in lb for lb in labels),
            f"expected a 'text'/'input' label in {labels}",
        )
        self.assertNotEqual(state.planned_action, "")
        self.assertEqual(state.reflection,
                         "screenshot shows an empty Notepad window")
        self.assertNotIn("fallback", state.raw_response)

        # Wire-format check: multipart 'image' + form 'prompt' + 'tier'
        call = mock_post.call_args
        self.assertEqual(call.args[0], "http://mock-gui-owl/analyze")
        self.assertIn("image", call.kwargs["files"])
        self.assertEqual(call.kwargs["data"]["tier"], "7b")
        self.assertEqual(call.kwargs["data"]["prompt"], "open notepad")


# ------------------------------------------------------------------
# analyze() — fallback paths
# ------------------------------------------------------------------
class AnalyzeFallbackTests(unittest.TestCase):

    def setUp(self):
        self.screenshot = _fake_screenshot()
        self.adapter = GUIOwlAdapter(
            model_tier="7b", endpoint_url="http://mock-gui-owl"
        )

    def _assert_fallback(self, state: ScreenState, expected_step: str):
        self.assertEqual(state.elements, ())
        self.assertEqual(state.planned_action, "")
        self.assertEqual(state.reflection, "")
        self.assertTrue(state.raw_response.get("fallback"))
        self.assertEqual(state.raw_response.get("failed_step"), expected_step)
        self.assertIn("error", state.raw_response)

    def test_connect_failure(self):
        with patch.object(
            adapter_mod.requests, "post",
            side_effect=requests.ConnectionError("refused"),
        ):
            state = self.adapter.analyze(self.screenshot)
        self._assert_fallback(state, "connect")

    def test_http_status_failure(self):
        with patch.object(
            adapter_mod.requests, "post",
            return_value=_mock_response(None, status_code=503),
        ):
            state = self.adapter.analyze(self.screenshot)
        self._assert_fallback(state, "http_status")

    def test_parse_json_failure(self):
        bad = MagicMock(status_code=200, text="<html>not json</html>")
        bad.json.side_effect = ValueError("not json")
        with patch.object(adapter_mod.requests, "post", return_value=bad):
            state = self.adapter.analyze(self.screenshot)
        self._assert_fallback(state, "parse_json")

    def test_parse_schema_failure_missing_field(self):
        with patch.object(
            adapter_mod.requests, "post",
            return_value=_mock_response({"only": "garbage"}),
        ):
            state = self.adapter.analyze(self.screenshot)
        self._assert_fallback(state, "parse_schema")

    def test_resolve_endpoint_failure_via_unknown_tier(self):
        # Bypass constructor validation to simulate a corrupt config state.
        a = GUIOwlAdapter(model_tier="7b", endpoint_url="http://mock")
        object.__setattr__(a, "_endpoint_override", None)
        object.__setattr__(a, "model_tier", "13b")
        state = a.analyze(self.screenshot)
        self._assert_fallback(state, "resolve_endpoint")


# ------------------------------------------------------------------
# Constructor validation
# ------------------------------------------------------------------
class ConstructorTests(unittest.TestCase):

    def test_rejects_unknown_tier(self):
        with self.assertRaises(ValueError):
            GUIOwlAdapter(model_tier="13b")

    def test_auto_invokes_detect(self):
        with patch.object(
            adapter_mod, "_detect_tier_from_vram", return_value="72b"
        ) as mock_detect:
            a = GUIOwlAdapter(model_tier="auto", endpoint_url="http://x")
        mock_detect.assert_called_once()
        self.assertEqual(a.model_tier, "72b")


# ------------------------------------------------------------------
# Mock-server integration tests — real HTTP round-trip
# ------------------------------------------------------------------
@pytest.mark.integration
class MockServerIntegrationTests(unittest.TestCase):
    """Exercises the adapter against a real local HTTP server speaking the
    GUI-Owl wire contract. Catches multipart-encoding / header / socket bugs
    that mocked `requests.post` can't surface.
    """

    server = None
    port = 0

    @classmethod
    def setUpClass(cls):
        from scripts.dev.mock_gui_owl_server import start_server_in_thread
        cls.server, cls.port = start_server_in_thread(port=0)

    @classmethod
    def tearDownClass(cls):
        from scripts.dev.mock_gui_owl_server import stop_server
        if cls.server is not None:
            stop_server(cls.server)

    def _adapter(self) -> GUIOwlAdapter:
        return GUIOwlAdapter(
            model_tier="7b",
            endpoint_url=f"http://127.0.0.1:{self.port}",
        )

    def test_round_trip_default_payload(self):
        state = self._adapter().analyze(_fake_screenshot(), prompt="open notepad")
        self.assertNotIn("fallback", state.raw_response)
        self.assertGreaterEqual(len(state.elements), 1)
        labels = [el.label.lower() for el in state.elements]
        self.assertTrue(any("text" in lb or "input" in lb for lb in labels))
        self.assertNotEqual(state.planned_action, "")

    def test_round_trip_with_real_screenshot(self):
        """Capture a real Notepad screenshot via 1-A and pipe it through."""
        if os.name != "nt":
            self.skipTest("real screenshot requires Windows")
        try:
            from phone_agent.windows.screenshot import get_screenshot as capture
        except ImportError as e:
            self.skipTest(f"1-A screenshot module unavailable: {e}")
        try:
            screenshot = capture()
        except Exception as e:
            self.skipTest(f"could not capture real screenshot: {e}")
        state = self._adapter().analyze(screenshot, prompt="describe the desktop")
        self.assertNotIn("fallback", state.raw_response)
        self.assertGreaterEqual(len(state.elements), 1)

    def test_fallback_when_server_dies(self):
        """Stop the server, fire a request, expect failed_step='connect'."""
        from scripts.dev.mock_gui_owl_server import start_server_in_thread, stop_server
        srv, port = start_server_in_thread(port=0)
        stop_server(srv)
        a = GUIOwlAdapter(model_tier="7b",
                          endpoint_url=f"http://127.0.0.1:{port}")
        state = a.analyze(_fake_screenshot())
        self.assertTrue(state.raw_response.get("fallback"))
        self.assertEqual(state.raw_response.get("failed_step"), "connect")

    def test_malformed_bbox_triggers_parse_schema_fallback(self):
        """Q4-B: server returns bbox with 3 ints — adapter must hit parse_schema fallback."""
        from scripts.dev.mock_gui_owl_server import (
            start_server_in_thread, stop_server, MALFORMED_BBOX_RESPONSE,
        )
        srv, port = start_server_in_thread(port=0, response=MALFORMED_BBOX_RESPONSE)
        try:
            a = GUIOwlAdapter(model_tier="7b",
                              endpoint_url=f"http://127.0.0.1:{port}")
            state = a.analyze(_fake_screenshot())
        finally:
            stop_server(srv)
        self.assertTrue(state.raw_response.get("fallback"))
        self.assertEqual(state.raw_response.get("failed_step"), "parse_schema")

    def test_malformed_bbox_negative_coords_still_parses(self):
        """Q4-B variant: bbox with 4 ints but negatives — currently allowed.

        We don't reject negative coords (some VLMs return offscreen elements
        deliberately). This test pins that decision: negative bbox coords are
        treated as success, not fallback. If we later decide to reject them,
        flip this test and update the parse_schema contract in the integration
        doc.
        """
        from scripts.dev.mock_gui_owl_server import start_server_in_thread, stop_server
        payload = {
            "elements": [{"label": "offscreen text", "bbox": [-10, -5, 100, 200],
                          "confidence": 0.6, "type": "text"}],
            "planned_action": "scroll right",
            "reflection": "element is partially offscreen",
            "raw": {"scenario": "negative_coords"},
        }
        srv, port = start_server_in_thread(port=0, response=payload)
        try:
            a = GUIOwlAdapter(model_tier="7b",
                              endpoint_url=f"http://127.0.0.1:{port}")
            state = a.analyze(_fake_screenshot())
        finally:
            stop_server(srv)
        self.assertNotIn("fallback", state.raw_response)
        self.assertEqual(state.elements[0].bbox, (-10, -5, 100, 200))


# ------------------------------------------------------------------
# Live integration test — opt-in via CLAWGUI_GUIOWL_LIVE=1
# ------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("CLAWGUI_GUIOWL_LIVE") != "1",
    reason="set CLAWGUI_GUIOWL_LIVE=1 to run against a real GUI-Owl backend",
)
class LiveIntegrationTests(unittest.TestCase):

    def test_real_endpoint_returns_screenstate(self):
        from phone_agent.windows.screenshot import get_screenshot as capture
        screenshot = capture()
        adapter = GUIOwlAdapter(model_tier="auto")
        state = adapter.analyze(
            screenshot, prompt="describe the visible Windows desktop"
        )
        self.assertIsInstance(state, ScreenState)
        self.assertFalse(
            state.raw_response.get("fallback"),
            f"live call hit fallback: {state.raw_response}",
        )
        self.assertGreater(len(state.elements), 0)
        self.assertNotEqual(state.planned_action, "")


if __name__ == "__main__":
    unittest.main()
