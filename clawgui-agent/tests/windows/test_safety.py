"""Unit tests for phone_agent.windows.safety (platform-independent parts).

The KillSwitch message pump and GetLastInputInfo polling require Windows;
those paths are smoke-checked behind a platform skip.  Hotkey parsing,
state tracking, and the countdown banner are tested everywhere.
"""
# Notes: docs/tests/windows/test_safety.md
from __future__ import annotations

import io
import os
import platform
import sys
import unittest
from unittest.mock import patch

# Ensure CLAWGUI_TEST_SAFETY default is preserved across tests
_ORIG_ENV = dict(os.environ)


def _reset_state():
    """Reset the module-level SafetyState between tests."""
    from phone_agent.windows import safety
    safety.STATE.current_step      = ""
    safety.STATE.next_step         = ""
    safety.STATE.aborted           = False
    safety.STATE.abort_reason      = ""
    safety.STATE.spawned_procs.clear()
    safety.STATE.cleanup_callbacks.clear()


class HotkeyParserTests(unittest.TestCase):

    def test_shift_right_default(self):
        from phone_agent.windows.safety import _parse_hotkey
        mods, vk = _parse_hotkey("shift+right")
        self.assertEqual(mods, 0x0004)        # MOD_SHIFT
        self.assertEqual(vk,   0x27)          # VK_RIGHT

    def test_ctrl_alt_f12_combo(self):
        from phone_agent.windows.safety import _parse_hotkey
        mods, vk = _parse_hotkey("ctrl+alt+f12")
        self.assertEqual(mods, 0x0001 | 0x0002)
        self.assertEqual(vk,   0x7B)

    def test_case_insensitive(self):
        from phone_agent.windows.safety import _parse_hotkey
        a = _parse_hotkey("Shift+Right")
        b = _parse_hotkey("SHIFT+RIGHT")
        self.assertEqual(a, b)

    def test_alphanumeric_keys(self):
        from phone_agent.windows.safety import _parse_hotkey
        _, vk_a = _parse_hotkey("ctrl+a")
        _, vk_9 = _parse_hotkey("alt+9")
        self.assertEqual(vk_a, ord("A"))
        self.assertEqual(vk_9, ord("9"))

    def test_empty_spec_raises(self):
        from phone_agent.windows.safety import _parse_hotkey
        with self.assertRaises(ValueError):
            _parse_hotkey("")

    def test_modifier_only_raises(self):
        from phone_agent.windows.safety import _parse_hotkey
        with self.assertRaises(ValueError):
            _parse_hotkey("shift+ctrl")

    def test_unknown_key_raises(self):
        from phone_agent.windows.safety import _parse_hotkey
        with self.assertRaises(ValueError):
            _parse_hotkey("shift+banana")

    def test_two_main_keys_raises(self):
        from phone_agent.windows.safety import _parse_hotkey
        with self.assertRaises(ValueError):
            _parse_hotkey("a+b")


class StateRegistrationTests(unittest.TestCase):

    def setUp(self):
        _reset_state()

    def test_register_process_appends(self):
        from phone_agent.windows import safety

        class _FakeProc:
            def poll(self): return None
        p = _FakeProc()
        safety.register_process(p)
        self.assertIn(p, safety.STATE.spawned_procs)

    def test_register_cleanup_appends(self):
        from phone_agent.windows import safety
        cb = lambda: None
        safety.register_cleanup(cb)
        self.assertIn(cb, safety.STATE.cleanup_callbacks)


class CountdownTests(unittest.TestCase):

    def test_countdown_zero_seconds_is_silent(self):
        from phone_agent.windows import safety
        buf = io.StringIO()
        with patch.object(sys, "stderr", buf):
            safety.countdown(seconds=0)
        self.assertEqual(buf.getvalue(), "")

    def test_countdown_writes_takeover_warning(self):
        from phone_agent.windows import safety
        buf = io.StringIO()
        with patch.object(sys, "stderr", buf), patch("time.sleep", lambda *_: None):
            safety.countdown(seconds=2, hotkey_label="shift+right")
        out = buf.getvalue()
        self.assertIn("take over this machine", out)
        self.assertIn("shift+right", out)
        self.assertIn("starting in 2", out)
        self.assertIn("starting in 1", out)
        self.assertIn("running.", out)


class PresenceMonitorTests(unittest.TestCase):

    def setUp(self):
        _reset_state()

    def test_no_input_seen_does_not_pause(self):
        from phone_agent.windows import safety
        # idle clock keeps growing → user is idle
        idles = iter([100, 200, 300])
        with patch.object(safety, "_idle_ms", lambda: next(idles)):
            pm = safety.PresenceMonitor()
            pm.mark_test_start()       # captures 100
            pm.wait_for_idle_or_abort()  # reads 200, 200>100 -> not seen, returns

    def test_user_input_then_idle_resumes(self):
        from phone_agent.windows import safety
        # mark_test_start captures 500;
        # wait_for_idle_or_abort sees current=100 (input!), then polls until >= threshold
        readings = iter([500, 100, 100, 800, 800])
        with patch.object(safety, "_idle_ms", lambda: next(readings)), \
             patch("time.sleep", lambda *_: None), \
             patch("time.monotonic", side_effect=[0.0, 0.1, 0.2, 0.3, 0.4]):
            pm = safety.PresenceMonitor(pause_seconds=10.0, idle_threshold_ms=500)
            pm.mark_test_start()
            pm.wait_for_idle_or_abort()  # should NOT raise

    def test_user_keeps_typing_aborts(self):
        from phone_agent.windows import safety
        # Always shows fresh input; idle never crosses threshold.
        with patch.object(safety, "_idle_ms", side_effect=[1000, 50, 50, 50, 50, 50, 50]), \
             patch("time.sleep", lambda *_: None), \
             patch("time.monotonic", side_effect=[0.0, 0.1, 6.0]):
            pm = safety.PresenceMonitor(pause_seconds=5.0, idle_threshold_ms=500)
            pm.mark_test_start()
            with self.assertRaises(safety.UserInterferenceAbort):
                pm.wait_for_idle_or_abort()
        self.assertTrue(safety.STATE.aborted)


class KillSwitchUnitTests(unittest.TestCase):
    """Non-platform parts: parsing in __init__, fire() side effects via patches."""

    def setUp(self):
        _reset_state()

    def test_init_parses_hotkey(self):
        from phone_agent.windows.safety import KillSwitch
        ks = KillSwitch("ctrl+f9")
        self.assertEqual(ks._mods, 0x0002)
        self.assertEqual(ks._vk,   0x78)

    def test_init_invalid_hotkey_raises(self):
        from phone_agent.windows.safety import KillSwitch
        with self.assertRaises(ValueError):
            KillSwitch("nonsense")

    def test_fire_sets_aborted_state_and_runs_callbacks(self):
        from phone_agent.windows import safety

        class _FakeProc:
            def __init__(self): self.killed = False
            def poll(self):     return None
            def kill(self):     self.killed = True

        proc = _FakeProc()
        safety.register_process(proc)

        called = []
        safety.register_cleanup(lambda: called.append("cb"))

        ks = safety.KillSwitch("shift+right")
        # Patch out OS-level effects + the os._exit call so the test process survives.
        with patch.object(safety, "_release_modifier_keys"), \
             patch.object(safety, "_recenter_cursor"), \
             patch.object(safety.os, "_exit") as mock_exit, \
             patch.object(sys, "stderr", io.StringIO()):
            ks._fire()

        self.assertTrue(safety.STATE.aborted)
        self.assertIn("shift+right", safety.STATE.abort_reason)
        self.assertTrue(proc.killed)
        self.assertEqual(called, ["cb"])
        mock_exit.assert_called_once_with(130)


@unittest.skipUnless(platform.system() == "Windows", "GetLastInputInfo is Windows-only")
class WindowsOnlyTests(unittest.TestCase):

    def test_idle_ms_returns_nonneg_int(self):
        from phone_agent.windows.safety import _idle_ms
        v = _idle_ms()
        self.assertIsInstance(v, int)
        self.assertGreaterEqual(v, 0)

    def test_killswitch_start_stop_smoke(self):
        from phone_agent.windows.safety import KillSwitch
        ks = KillSwitch("ctrl+alt+f9")  # unlikely to collide with anything
        ks.start()
        try:
            self.assertIsNotNone(ks._thread)
            self.assertTrue(ks._thread.is_alive())
        finally:
            ks.stop()


def tearDownModule():  # noqa: N802
    # Restore only CLAWGUI_* vars; touching the broader env breaks pytest's
    # own PYTEST_CURRENT_TEST bookkeeping.
    for k in [k for k in os.environ if k.startswith("CLAWGUI_")]:
        if k not in _ORIG_ENV:
            del os.environ[k]
    for k, v in _ORIG_ENV.items():
        if k.startswith("CLAWGUI_"):
            os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
