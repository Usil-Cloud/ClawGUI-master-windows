"""Tests for phone_agent/windows/device.py -- Feature 1-B.

Test structure
--------------
Unit tests (MockedDeviceTests)
    Patch sys.modules so lazy "import pyautogui" / "import win32gui" calls
    inside the production functions pick up mocks automatically.  Runs on
    any OS without a display.

Integration tests (IntegrationDeviceTests)
    Require a real Windows machine with pyautogui + pywin32 installed.
    Skipped automatically on non-Windows or when dependencies are absent.
    Each test is designed to be safe: cursor moves stay near (100, 100),
    Notepad is opened and closed per test, long_press duration is 200 ms.

Run all tests:
    python -m pytest tests/windows/test_device.py -v

Run only unit tests (safe on any OS):
    python -m pytest tests/windows/test_device.py -v -k "not Integration"

Run only integration tests (Windows with deps):
    python -m pytest tests/windows/test_device.py -v -k "Integration"
"""
# Notes: docs/tests/windows/test_device.md
from __future__ import annotations

import platform
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Capability detection — must run BEFORE any stubs are installed so we
# distinguish "real pywin32 available" from "stub imported successfully".
# ---------------------------------------------------------------------------

_ON_WINDOWS    = platform.system() == "Windows"
_HAS_PYAUTOGUI = False
_HAS_WIN32GUI  = False

if _ON_WINDOWS:
    try:
        import pyautogui as _pg   # noqa: F401
        _HAS_PYAUTOGUI = True
    except (ImportError, Exception):
        pass
    try:
        import win32gui as _w32   # noqa: F401
        _HAS_WIN32GUI = True
    except (ImportError, Exception):
        pass

# ---------------------------------------------------------------------------
# Pre-stub heavy optional deps so device.py imports succeed everywhere.
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
    GetForegroundWindow=lambda: 1,
    GetWindowText=lambda h: "Stubbed Window",
    IsWindowVisible=lambda h: True,
    EnumWindows=lambda cb, x: None,
    GetWindowRect=lambda h: (0, 0, 1920, 1080),
)
_stub_if_missing("pyautogui",
    click=lambda x, y: None,
    doubleClick=lambda x, y: None,
    rightClick=lambda x, y: None,
    mouseDown=lambda x, y: None,
    mouseUp=lambda x, y: None,
    dragTo=lambda x, y, duration=0.5, button="left": None,
    moveTo=lambda x, y: None,
    scroll=lambda amount, x=0, y=0: None,
    hotkey=lambda *keys: None,
    press=lambda key: None,
    typewrite=lambda text, interval=0.05: None,
    position=lambda: (100, 100),
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
_stub_if_missing("phone_agent.config.apps_windows",
    APP_PACKAGES_WINDOWS={
        "Notepad": "notepad.exe",
        "notepad": "notepad.exe",
        "Calculator": "calc.exe",
    },
)

# Stub openai + the high-level agent modules so phone_agent/__init__.py
# doesn't choke when we do 'from phone_agent.windows import device'.
_stub_if_missing("openai", OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client",
    ModelClient=MagicMock,
    ModelConfig=MagicMock,
)
_stub_if_missing("phone_agent.model",
    ModelClient=MagicMock,
    ModelConfig=MagicMock,
)
_stub_if_missing("phone_agent.agent", PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios", IOSPhoneAgent=MagicMock)

from phone_agent.windows import device as dv  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────

def _pyautogui_mock():
    """Return a fully wired MagicMock for pyautogui."""
    pg = MagicMock()
    pg.position.return_value = (100, 100)
    return pg


def _win32gui_mock(foreground_title: str = "Test Window"):
    w32 = MagicMock()
    w32.GetForegroundWindow.return_value = 42
    w32.GetWindowText.return_value = foreground_title
    return w32


# ── Unit tests ────────────────────────────────────────────────────────────────

class MockedDeviceTests(unittest.TestCase):
    """All 7 action functions + helpers, tested with mocked dependencies."""

    # -- tap ------------------------------------------------------------------

    def test_tap_calls_click_with_coordinates(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.tap(200, 300)
        pg.click.assert_called_once_with(200, 300)

    def test_tap_applies_delay(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}), \
             patch("time.sleep") as mock_sleep:
            dv.tap(10, 20, delay=0.5)
        mock_sleep.assert_called_once_with(0.5)

    def test_tap_no_delay_by_default(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}), \
             patch("time.sleep") as mock_sleep:
            dv.tap(10, 20)
        mock_sleep.assert_not_called()

    # -- double_tap -----------------------------------------------------------

    def test_double_tap_calls_doubleClick(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.double_tap(50, 60)
        pg.doubleClick.assert_called_once_with(50, 60)

    # -- right_click ----------------------------------------------------------

    def test_right_click_calls_rightClick(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.right_click(70, 80)
        pg.rightClick.assert_called_once_with(70, 80)

    # -- long_press -----------------------------------------------------------

    def test_long_press_calls_mouseDown_sleep_mouseUp(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}), \
             patch("time.sleep") as mock_sleep:
            dv.long_press(100, 200, duration_ms=500)
        pg.mouseDown.assert_called_once_with(100, 200)
        pg.mouseUp.assert_called_once_with(100, 200)
        # First sleep is the press duration; may have a second if delay= is set.
        args_list = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertIn(0.5, args_list)  # 500 ms / 1000

    def test_long_press_default_duration_is_3000ms(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}), \
             patch("time.sleep") as mock_sleep:
            dv.long_press(0, 0)
        args_list = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertIn(3.0, args_list)

    # -- swipe ----------------------------------------------------------------

    def test_swipe_calls_moveTo_then_dragTo(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.swipe(10, 20, 300, 400, duration_ms=600)
        pg.moveTo.assert_called_once_with(10, 20)
        pg.dragTo.assert_called_once_with(300, 400, duration=0.6, button="left")

    def test_swipe_default_duration_500ms(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.swipe(0, 0, 100, 100)
        _, kwargs = pg.dragTo.call_args
        self.assertAlmostEqual(kwargs["duration"], 0.5)

    # -- scroll ---------------------------------------------------------------

    def test_scroll_down_passes_negative_clicks(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.scroll(400, 300, clicks=5, direction="down")
        pg.scroll.assert_called_once_with(-5, x=400, y=300)

    def test_scroll_up_passes_positive_clicks(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.scroll(400, 300, clicks=3, direction="up")
        pg.scroll.assert_called_once_with(3, x=400, y=300)

    def test_scroll_default_direction_is_down(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            dv.scroll(0, 0)
        amount = pg.scroll.call_args.args[0]
        self.assertLess(amount, 0)  # negative = down

    # -- launch_app -----------------------------------------------------------

    def test_launch_app_known_name_uses_subprocess(self):
        with patch("subprocess.Popen") as mock_popen:
            result = dv.launch_app("Notepad")
        mock_popen.assert_called_once_with(["notepad.exe"])
        self.assertTrue(result)

    def test_launch_app_unknown_name_returns_false_when_unresolvable(self):
        """Unknown app that AppResolver cannot resolve returns False; no direct Popen."""
        from phone_agent.windows.app_resolver import AppResolver
        with patch.object(AppResolver, "resolve", return_value=None) as mock_resolve:
            result = dv.launch_app("MyCustomApp")
        mock_resolve.assert_called_once_with("MyCustomApp")
        self.assertFalse(result)

    def test_launch_app_subprocess_failure_falls_back_to_start_menu(self):
        pg = _pyautogui_mock()
        with patch("subprocess.Popen", side_effect=FileNotFoundError), \
             patch.dict("sys.modules", {"pyautogui": pg}):
            result = dv.launch_app("UnknownApp99")
        # Hotkey win + typewrite + enter is the start-menu fallback
        pg.hotkey.assert_called()
        self.assertTrue(result)  # start-menu fallback always returns True

    # -- get_current_app / _local_get_current_app ----------------------------

    def test_get_current_app_returns_foreground_title(self):
        w32 = _win32gui_mock("Notepad - Untitled")
        with patch.dict("sys.modules", {"win32gui": w32}):
            title = dv._local_get_current_app()
        self.assertEqual(title, "Notepad - Untitled")

    def test_get_current_app_returns_unknown_on_exception(self):
        w32 = MagicMock()
        w32.GetForegroundWindow.side_effect = Exception("no window")
        with patch.dict("sys.modules", {"win32gui": w32}):
            title = dv._local_get_current_app()
        self.assertEqual(title, "Unknown")

    def test_get_current_app_empty_text_returns_unknown(self):
        w32 = _win32gui_mock("")
        with patch.dict("sys.modules", {"win32gui": w32}):
            title = dv._local_get_current_app()
        self.assertEqual(title, "Unknown")


# ── Integration tests (Windows-only) ─────────────────────────────────────────

_SKIP = not (_ON_WINDOWS and _HAS_PYAUTOGUI and _HAS_WIN32GUI)
_WHY  = (
    f"Requires Windows + pyautogui + pywin32 "
    f"(Windows={_ON_WINDOWS}, pyautogui={_HAS_PYAUTOGUI}, win32gui={_HAS_WIN32GUI})"
)


@unittest.skipIf(_SKIP, _WHY)
class IntegrationDeviceTests(unittest.TestCase):
    """Live execution tests.  Runs only on Windows with dependencies installed.

    Safety constraints
    ------------------
    - All cursor interactions stay near (100, 100) on the desktop.
    - long_press uses 200 ms to avoid holding for a perceivable duration.
    - Notepad is launched fresh and killed after the class finishes.
    - pyautogui.FAILSAFE is kept True (move to top-left corner aborts).
    """

    NOTEPAD_TITLE = "Notepad"
    _proc: subprocess.Popen | None = None

    @classmethod
    def setUpClass(cls):
        import pyautogui
        pyautogui.FAILSAFE = True  # safety net: move to (0,0) to abort

    def setUp(self):
        import pyautogui
        pyautogui.moveTo(200, 200)  # ensure cursor is never at a failsafe corner

    @classmethod
    def tearDownClass(cls):
        if cls._proc is not None:
            cls._proc.kill()
            cls._proc.wait(timeout=3)

    def _open_notepad(self) -> subprocess.Popen:
        """Open Notepad, wait for the window to appear, and bring it to focus."""
        import win32gui
        proc = subprocess.Popen(["notepad.exe"])
        hwnd = None
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            found = []
            def _cb(h, _):
                if win32gui.IsWindowVisible(h) and "Notepad" in win32gui.GetWindowText(h):
                    found.append(h)
            win32gui.EnumWindows(_cb, None)
            if found:
                hwnd = found[0]
                break
            time.sleep(0.1)
        if hwnd:
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.2)
            except Exception:
                pass
        return proc

    def _close_notepad(self, proc: subprocess.Popen) -> None:
        proc.kill()
        proc.wait(timeout=3)

    # -- smoke: tap -----------------------------------------------------------

    def test_tap_moves_cursor_to_position(self):
        """tap(100, 100) should move the cursor to approximately (100, 100)."""
        import pyautogui
        dv.tap(100, 100)
        x, y = pyautogui.position()
        self.assertAlmostEqual(x, 100, delta=5)
        self.assertAlmostEqual(y, 100, delta=5)

    # -- smoke: double_tap ----------------------------------------------------

    def test_double_tap_executes_without_exception(self):
        dv.double_tap(100, 100)  # should not raise

    # -- smoke: right_click ---------------------------------------------------

    def test_right_click_executes_without_exception(self):
        """Right-click at (100, 100) on desktop; close the context menu after."""
        import pyautogui
        dv.right_click(100, 100)
        time.sleep(0.3)
        pyautogui.press("escape")  # dismiss context menu

    # -- smoke: long_press ----------------------------------------------------

    def test_long_press_holds_for_specified_duration(self):
        """long_press with 200 ms should take at least 200 ms wall time."""
        start = time.monotonic()
        dv.long_press(100, 100, duration_ms=200)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.18)  # allow 20 ms tolerance

    # -- smoke: swipe ---------------------------------------------------------

    def test_swipe_executes_without_exception(self):
        dv.swipe(100, 100, 200, 100, duration_ms=300)  # short horizontal drag

    # -- smoke: scroll --------------------------------------------------------

    def test_scroll_executes_without_exception(self):
        dv.scroll(100, 100, clicks=2, direction="down")

    # -- smoke: launch_app + get_current_app ----------------------------------

    def test_launch_notepad_returns_true_and_window_appears(self):
        """launch_app('Notepad') should return True and a Notepad window opens."""
        result = dv.launch_app("Notepad")
        self.assertTrue(result)

        # Wait up to 5 s for the window to appear
        deadline = time.monotonic() + 5.0
        import win32gui
        found = False
        while time.monotonic() < deadline:
            handles = []
            def _cb(h, _):
                if win32gui.IsWindowVisible(h) and "Notepad" in win32gui.GetWindowText(h):
                    handles.append(h)
            win32gui.EnumWindows(_cb, None)
            if handles:
                found = True
                break
            time.sleep(0.15)

        self.assertTrue(found, "Notepad window did not appear within 5 seconds")

        # Kill only the Notepad PID we just launched (not any shared session proc).
        if handles:
            try:
                import win32process
                _, pid = win32process.GetWindowThreadProcessId(handles[0])
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            except Exception:
                pass

    def test_get_current_app_returns_nonempty_string(self):
        """_local_get_current_app() should return a non-empty string."""
        title = dv._local_get_current_app()
        self.assertIsInstance(title, str)
        self.assertGreater(len(title), 0)

    def test_get_current_app_matches_foreground_when_notepad_focused(self):
        """Open Notepad, bring it to focus, verify _local_get_current_app contains 'Notepad'."""
        import win32gui
        proc = self._open_notepad()
        try:
            # Give Notepad a moment to take focus
            time.sleep(0.5)
            title = dv._local_get_current_app()
            self.assertIn("Notepad", title,
                          f"Expected 'Notepad' in foreground title, got: {title!r}")
        finally:
            self._close_notepad(proc)


if __name__ == "__main__":
    unittest.main()
