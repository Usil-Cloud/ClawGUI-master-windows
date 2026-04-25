"""Tests for phone_agent/windows/window_manager.py -- Feature 1-D.

Test structure
--------------
Unit tests (MockedWindowManagerTests)
    Patch sys.modules so lazy imports inside production functions pick up
    mocks automatically.  Runs on any OS without a display or win32 libs.

Integration tests (IntegrationWindowManagerTests)
    Require a real Windows machine with pywin32 installed.
    Opens Notepad, exercises list_windows / focus_window / minimize /
    maximize, then closes.  Skipped automatically on non-Windows or when
    dependencies are absent.

Run all tests:
    python -m pytest tests/windows/test_window_manager.py -v

Run only unit tests (safe on any OS):
    python -m pytest tests/windows/test_window_manager.py -v -k "not Integration"

Run only integration tests (Windows with deps):
    python -m pytest tests/windows/test_window_manager.py -v -k "Integration"
"""
from __future__ import annotations

import platform
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Pre-stub heavy optional deps so window_manager.py imports succeed everywhere.
# ---------------------------------------------------------------------------

def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _stub_if_missing(name: str, **attrs) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except ImportError:
        _stub(name, **attrs)


_stub_if_missing("win32gui",
    IsWindowVisible=lambda h: True,
    GetWindowText=lambda h: "Stubbed Window",
    EnumWindows=lambda cb, x: None,
    GetWindowRect=lambda h: (0, 0, 800, 600),
    SetForegroundWindow=lambda h: None,
    IsIconic=lambda h: False,
    ShowWindow=lambda h, cmd: None,
    PostMessage=lambda h, msg, w, l: None,
)
_stub_if_missing("win32con",
    SW_MINIMIZE=6,
    SW_MAXIMIZE=3,
    SW_RESTORE=9,
    SC_CLOSE=0xF060,
    WM_CLOSE=0x0010,
)
_stub_if_missing("phone_agent.windows.connection",
    is_local=lambda device_id: True,
    post=lambda *a, **kw: {},
    ConnectionMode=object,
    DeviceInfo=object,
    WindowsConnection=object,
    verify_connection=lambda *a, **kw: True,
    list_devices=lambda: [],
)

# Silence high-level phone_agent imports
_stub_if_missing("openai", OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent", PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios", IOSPhoneAgent=MagicMock)

import phone_agent.windows.window_manager as wm  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _win32gui_mock(
    visible: bool = True,
    title: str = "Test Window",
    rect: tuple = (0, 0, 800, 600),
    is_iconic: bool = False,
) -> MagicMock:
    g = MagicMock()
    g.IsWindowVisible.return_value = visible
    g.GetWindowText.return_value = title
    g.GetWindowRect.return_value = rect
    g.IsIconic.return_value = is_iconic
    return g


def _win32con_mock() -> MagicMock:
    c = MagicMock()
    c.SW_MINIMIZE = 6
    c.SW_MAXIMIZE = 3
    c.SW_RESTORE = 9
    c.WM_CLOSE = 0x0010
    return c


# ── Unit tests ────────────────────────────────────────────────────────────────

class MockedWindowManagerTests(unittest.TestCase):
    """All window manager functions tested with mocked win32gui + win32con."""

    # -- list_windows: filtering ----------------------------------------------

    def test_list_windows_returns_windowinfo_objects(self):
        g = _win32gui_mock()
        windows_found = []

        def fake_enum(cb, _):
            cb(1001, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "My Window"
        g.GetWindowRect.return_value = (10, 20, 800, 600)

        with patch.dict("sys.modules", {"win32gui": g}):
            result = wm._local_list_windows()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].hwnd, 1001)
        self.assertEqual(result[0].title, "My Window")
        self.assertTrue(result[0].visible)
        self.assertEqual(result[0].rect, (10, 20, 800, 600))

    def test_list_windows_excludes_invisible_windows(self):
        g = _win32gui_mock()

        def fake_enum(cb, _):
            cb(1001, None)  # invisible
            cb(1002, None)  # visible

        g.EnumWindows.side_effect = fake_enum
        g.GetWindowText.return_value = "A Window"

        visible_map = {1001: False, 1002: True}
        g.IsWindowVisible.side_effect = lambda h: visible_map.get(h, False)
        g.GetWindowRect.return_value = (0, 0, 800, 600)

        with patch.dict("sys.modules", {"win32gui": g}):
            result = wm._local_list_windows()

        hwnds = [w.hwnd for w in result]
        self.assertNotIn(1001, hwnds)
        self.assertIn(1002, hwnds)

    def test_list_windows_excludes_empty_title_windows(self):
        g = _win32gui_mock()

        def fake_enum(cb, _):
            cb(2001, None)  # empty title
            cb(2002, None)  # real title

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        title_map = {2001: "", 2002: "Real Title"}
        g.GetWindowText.side_effect = lambda h: title_map.get(h, "")
        g.GetWindowRect.return_value = (0, 0, 100, 100)

        with patch.dict("sys.modules", {"win32gui": g}):
            result = wm._local_list_windows()

        hwnds = [w.hwnd for w in result]
        self.assertNotIn(2001, hwnds)
        self.assertIn(2002, hwnds)

    def test_list_windows_includes_rect_in_windowinfo(self):
        g = _win32gui_mock()
        expected_rect = (50, 100, 1024, 768)

        def fake_enum(cb, _):
            cb(3001, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "RectWindow"
        g.GetWindowRect.return_value = expected_rect

        with patch.dict("sys.modules", {"win32gui": g}):
            result = wm._local_list_windows()

        self.assertEqual(result[0].rect, expected_rect)

    def test_list_windows_returns_empty_on_enum_exception(self):
        g = _win32gui_mock()
        g.EnumWindows.side_effect = OSError("win32 error")

        with patch.dict("sys.modules", {"win32gui": g}):
            result = wm._local_list_windows()

        self.assertEqual(result, [])

    def test_list_windows_multiple_visible_windows(self):
        g = _win32gui_mock()
        hwnds_in = [100, 101, 102]

        def fake_enum(cb, _):
            for h in hwnds_in:
                cb(h, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Window"
        g.GetWindowRect.return_value = (0, 0, 800, 600)

        with patch.dict("sys.modules", {"win32gui": g}):
            result = wm._local_list_windows()

        self.assertEqual(len(result), 3)

    # -- focus_window ---------------------------------------------------------

    def test_focus_window_returns_true_on_match(self):
        g = _win32gui_mock(is_iconic=False)
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(5001, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Notepad"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_focus("notepad")

        self.assertTrue(result)
        g.SetForegroundWindow.assert_called_once_with(5001)

    def test_focus_window_returns_false_on_no_match(self):
        g = _win32gui_mock()
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(5002, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Calculator"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_focus("nonexistent_xyz")

        self.assertFalse(result)
        g.SetForegroundWindow.assert_not_called()

    def test_focus_window_restores_minimized_window(self):
        g = _win32gui_mock(is_iconic=True)
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(5003, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Notepad"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_focus("Notepad")

        self.assertTrue(result)
        g.ShowWindow.assert_called_once_with(5003, c.SW_RESTORE)
        g.SetForegroundWindow.assert_called_once_with(5003)

    def test_focus_window_case_insensitive_partial_match(self):
        g = _win32gui_mock(is_iconic=False)
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(5004, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Untitled - Notepad"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_focus("note")

        self.assertTrue(result)

    def test_focus_window_no_exception_on_no_match(self):
        g = _win32gui_mock()
        c = _win32con_mock()
        g.EnumWindows.side_effect = lambda cb, _: None  # no windows

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            try:
                result = wm._local_focus("nonexistent_xyz")
            except Exception as exc:
                self.fail(f"focus raised unexpectedly: {exc}")

        self.assertFalse(result)

    # -- minimize_window ------------------------------------------------------

    def test_minimize_window_calls_sw_minimize(self):
        g = _win32gui_mock()
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(6001, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Notepad"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_set_window_state("Notepad", "minimize")

        self.assertTrue(result)
        g.ShowWindow.assert_called_once_with(6001, c.SW_MINIMIZE)

    def test_minimize_window_returns_false_on_no_match(self):
        g = _win32gui_mock()
        c = _win32con_mock()
        g.EnumWindows.side_effect = lambda cb, _: None

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_set_window_state("nonexistent_xyz", "minimize")

        self.assertFalse(result)
        g.ShowWindow.assert_not_called()

    # -- maximize_window ------------------------------------------------------

    def test_maximize_window_calls_sw_maximize(self):
        g = _win32gui_mock()
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(7001, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Notepad"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_set_window_state("Notepad", "maximize")

        self.assertTrue(result)
        g.ShowWindow.assert_called_once_with(7001, c.SW_MAXIMIZE)

    def test_maximize_window_returns_false_on_no_match(self):
        g = _win32gui_mock()
        c = _win32con_mock()
        g.EnumWindows.side_effect = lambda cb, _: None

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_set_window_state("nonexistent_xyz", "maximize")

        self.assertFalse(result)

    # -- close_window ---------------------------------------------------------

    def test_close_window_posts_wm_close_message(self):
        g = _win32gui_mock()
        c = _win32con_mock()

        def fake_enum(cb, _):
            cb(8001, None)

        g.EnumWindows.side_effect = fake_enum
        g.IsWindowVisible.return_value = True
        g.GetWindowText.return_value = "Notepad"

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_set_window_state("Notepad", "close")

        self.assertTrue(result)
        g.PostMessage.assert_called_once_with(8001, c.WM_CLOSE, 0, 0)

    def test_close_window_returns_false_on_no_match(self):
        g = _win32gui_mock()
        c = _win32con_mock()
        g.EnumWindows.side_effect = lambda cb, _: None

        with patch.dict("sys.modules", {"win32gui": g, "win32con": c}):
            result = wm._local_set_window_state("nonexistent_xyz", "close")

        self.assertFalse(result)
        g.PostMessage.assert_not_called()

    # -- remote delegation ----------------------------------------------------

    def test_list_windows_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={
            "windows": [{"hwnd": 9001, "title": "Remote Window", "visible": True, "rect": [0, 0, 800, 600]}]
        })
        import importlib
        mod = importlib.import_module("phone_agent.windows.window_manager")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            result = mod.list_windows(device_id="192.168.1.10")
        mock_post.assert_called_once_with("192.168.1.10", "/api/windows/list", {})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].hwnd, 9001)
        self.assertEqual(result[0].title, "Remote Window")
        self.assertEqual(result[0].rect, (0, 0, 800, 600))

    def test_focus_window_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={"ok": True})
        import importlib
        mod = importlib.import_module("phone_agent.windows.window_manager")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            result = mod.focus_window("Notepad", device_id="192.168.1.10")
        mock_post.assert_called_once_with("192.168.1.10", "/api/action/focus_window", {"title": "Notepad"})
        self.assertTrue(result)

    def test_minimize_window_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={"ok": True})
        import importlib
        mod = importlib.import_module("phone_agent.windows.window_manager")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            result = mod.minimize_window("Notepad", device_id="192.168.1.10")
        mock_post.assert_called_once_with("192.168.1.10", "/api/windows/minimize", {"title": "Notepad"})
        self.assertTrue(result)

    def test_maximize_window_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={"ok": True})
        import importlib
        mod = importlib.import_module("phone_agent.windows.window_manager")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            result = mod.maximize_window("Notepad", device_id="192.168.1.10")
        mock_post.assert_called_once_with("192.168.1.10", "/api/windows/maximize", {"title": "Notepad"})
        self.assertTrue(result)

    def test_close_window_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={"ok": True})
        import importlib
        mod = importlib.import_module("phone_agent.windows.window_manager")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            result = mod.close_window("Notepad", device_id="192.168.1.10")
        mock_post.assert_called_once_with("192.168.1.10", "/api/windows/close", {"title": "Notepad"})
        self.assertTrue(result)


# ── Integration tests (Windows-only) ─────────────────────────────────────────

_ON_WINDOWS = platform.system() == "Windows"
_HAS_WIN32 = False

if _ON_WINDOWS:
    try:
        import win32gui as _wg   # noqa: F401
        import win32con as _wc   # noqa: F401
        _HAS_WIN32 = True
    except ImportError:
        pass

_SKIP = not (_ON_WINDOWS and _HAS_WIN32)
_WHY = (
    f"Requires Windows + pywin32 "
    f"(Windows={_ON_WINDOWS}, win32={_HAS_WIN32})"
)


@unittest.skipIf(_SKIP, _WHY)
class IntegrationWindowManagerTests(unittest.TestCase):
    """Live window manager tests.  Runs only on Windows with pywin32.

    Safety constraints
    ------------------
    - Notepad is opened once for the class and killed in tearDownClass.
    - All state-change tests restore the window afterward.
    - focus_window('nonexistent_xyz') must not raise.
    """

    _proc: subprocess.Popen | None = None

    @classmethod
    def setUpClass(cls):
        try:
            from conftest import _shared_notepad
            shared = _shared_notepad[0]
        except ImportError:
            shared = None
        if shared is not None:
            cls._proc = shared
            cls._owns_proc = False
        else:
            cls._proc = subprocess.Popen(["notepad.exe"])
            cls._owns_proc = True
        cls._wait_for_notepad()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_proc", True) and cls._proc is not None:
            cls._proc.kill()
            cls._proc.wait(timeout=3)

    @classmethod
    def _wait_for_notepad(cls, timeout: float = 5.0) -> None:
        import win32gui
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = []
            def _cb(h, _):
                if win32gui.IsWindowVisible(h) and "Notepad" in win32gui.GetWindowText(h):
                    found.append(h)
            win32gui.EnumWindows(_cb, None)
            if found:
                return
            time.sleep(0.1)
        raise RuntimeError("Notepad did not appear within timeout")

    # -- list_windows ---------------------------------------------------------

    def test_list_windows_returns_nonempty_list(self):
        result = wm.list_windows()
        self.assertGreater(len(result), 0)

    def test_list_windows_finds_notepad(self):
        result = wm.list_windows()
        titles = [w.title for w in result]
        self.assertTrue(
            any("Notepad" in t for t in titles),
            f"Notepad not found in: {titles}",
        )

    def test_list_windows_all_visible(self):
        result = wm.list_windows()
        for w in result:
            self.assertTrue(w.visible, f"Window {w.title!r} marked invisible in list")

    def test_list_windows_all_have_nonempty_titles(self):
        result = wm.list_windows()
        for w in result:
            self.assertTrue(w.title, f"Window hwnd={w.hwnd} has empty title")

    def test_list_windows_windowinfo_has_rect(self):
        result = wm.list_windows()
        notepad = next((w for w in result if "Notepad" in w.title), None)
        self.assertIsNotNone(notepad, "Notepad not found in list_windows()")
        self.assertIsInstance(notepad.rect, tuple)
        self.assertEqual(len(notepad.rect), 4)

    def test_list_windows_notepad_has_valid_hwnd(self):
        result = wm.list_windows()
        notepad = next((w for w in result if "Notepad" in w.title), None)
        self.assertIsNotNone(notepad)
        self.assertGreater(notepad.hwnd, 0)

    # -- focus_window ---------------------------------------------------------

    def test_focus_window_exact_match_returns_true(self):
        result = wm.focus_window("Notepad")
        time.sleep(0.2)
        self.assertTrue(result)

    def test_focus_window_partial_lowercase_returns_true(self):
        """focus_window('note') must match 'Untitled - Notepad' case-insensitively."""
        result = wm.focus_window("note")
        time.sleep(0.2)
        self.assertTrue(result)

    def test_focus_window_brings_notepad_to_foreground(self):
        import win32gui
        wm.focus_window("Notepad")
        time.sleep(0.3)
        fg_hwnd = win32gui.GetForegroundWindow()
        fg_title = win32gui.GetWindowText(fg_hwnd)
        self.assertIn("Notepad", fg_title, f"Foreground window is {fg_title!r}, not Notepad")

    def test_focus_window_nonexistent_returns_false(self):
        result = wm.focus_window("nonexistent_xyz")
        self.assertFalse(result)

    def test_focus_window_nonexistent_does_not_raise(self):
        try:
            wm.focus_window("nonexistent_xyz_absolutely_not_a_window")
        except Exception as exc:
            self.fail(f"focus_window raised unexpectedly: {exc}")

    # -- minimize_window ------------------------------------------------------

    def test_minimize_window_returns_true(self):
        wm.focus_window("Notepad")
        time.sleep(0.2)
        result = wm.minimize_window("Notepad")
        time.sleep(0.3)
        self.assertTrue(result)
        # Restore for subsequent tests
        wm.focus_window("Notepad")
        time.sleep(0.2)

    def test_minimize_window_changes_window_state(self):
        import win32gui
        wm.focus_window("Notepad")
        time.sleep(0.2)
        wm.minimize_window("Notepad")
        time.sleep(0.4)
        # Find Notepad hwnd and verify it is now iconic (minimized)
        found = []
        def _cb(h, _):
            if "Notepad" in win32gui.GetWindowText(h):
                found.append(h)
        win32gui.EnumWindows(_cb, None)
        self.assertTrue(found, "Notepad hwnd not found")
        self.assertTrue(win32gui.IsIconic(found[0]), "Notepad is not minimized")
        # Restore for subsequent tests
        wm.focus_window("Notepad")
        time.sleep(0.3)

    def test_minimize_window_nonexistent_returns_false(self):
        result = wm.minimize_window("nonexistent_xyz")
        self.assertFalse(result)

    # -- maximize_window ------------------------------------------------------

    def test_maximize_window_returns_true(self):
        wm.focus_window("Notepad")
        time.sleep(0.2)
        result = wm.maximize_window("Notepad")
        time.sleep(0.3)
        self.assertTrue(result)
        # Restore normal state
        wm.focus_window("Notepad")
        time.sleep(0.2)

    def test_maximize_window_changes_window_state(self):
        import win32gui
        import win32con
        wm.focus_window("Notepad")
        time.sleep(0.2)
        wm.maximize_window("Notepad")
        time.sleep(0.4)
        found = []
        def _cb(h, _):
            if "Notepad" in win32gui.GetWindowText(h):
                found.append(h)
        win32gui.EnumWindows(_cb, None)
        self.assertTrue(found, "Notepad hwnd not found")
        placement = win32gui.GetWindowPlacement(found[0])
        # showCmd == SW_SHOWMAXIMIZED (3) when window is maximized
        self.assertEqual(placement[1], win32con.SW_SHOWMAXIMIZED,
                         f"Expected maximized (3), got {placement[1]}")
        # Restore
        wm.focus_window("Notepad")
        time.sleep(0.2)

    def test_maximize_window_nonexistent_returns_false(self):
        result = wm.maximize_window("nonexistent_xyz")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
