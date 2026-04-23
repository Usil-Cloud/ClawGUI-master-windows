"""Tests for phone_agent/windows/input.py -- Feature 1-C.

Test structure
--------------
Unit tests (MockedInputTests)
    Patch sys.modules so lazy imports inside production functions pick up
    mocks automatically.  Runs on any OS without a display or clipboard.

Integration tests (IntegrationInputTests)
    Require a real Windows machine with pyautogui + pywin32 installed.
    Opens Notepad, types text, verifies clipboard contents, then closes.
    Skipped automatically on non-Windows or when dependencies are absent.

Run all tests:
    python -m pytest tests/windows/test_input.py -v

Run only unit tests (safe on any OS):
    python -m pytest tests/windows/test_input.py -v -k "not Integration"

Run only integration tests (Windows with deps):
    python -m pytest tests/windows/test_input.py -v -k "Integration"
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
# Pre-stub heavy optional deps so input.py imports succeed everywhere.
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
    SetForegroundWindow=lambda h: None,
)
_stub_if_missing("win32con", WM_GETTEXT=0x000D, WM_GETTEXTLENGTH=0x000E)
_stub_if_missing("pyautogui",
    hotkey=lambda *keys: None,
    press=lambda key: None,
    typewrite=lambda text, interval=0.05: None,
    click=lambda x, y: None,
    moveTo=lambda x, y: None,
    position=lambda: (0, 0),
    FAILSAFE=True,
)
_stub_if_missing("win32clipboard",
    OpenClipboard=lambda: None,
    CloseClipboard=lambda: None,
    EmptyClipboard=lambda: None,
    SetClipboardData=lambda fmt, data: None,
    GetClipboardData=lambda fmt: "",
    CF_UNICODETEXT=13,
)
_stub_if_missing("mss",
    mss=MagicMock,
)
_stub_if_missing("PIL", Image=MagicMock)
_stub_if_missing("PIL.Image", open=MagicMock, frombytes=MagicMock)
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
        "Calculator": "calc.exe",
    },
)

# Silence high-level phone_agent imports
_stub_if_missing("openai", OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent", PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios", IOSPhoneAgent=MagicMock)

import phone_agent.windows.input as inp  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────

def _pyautogui_mock() -> MagicMock:
    pg = MagicMock()
    return pg


def _win32clipboard_mock(cf_unicodetext: int = 13) -> MagicMock:
    cb = MagicMock()
    cb.CF_UNICODETEXT = cf_unicodetext
    return cb


# ── Unit tests ────────────────────────────────────────────────────────────────

class MockedInputTests(unittest.TestCase):
    """All keyboard functions tested with mocked pyautogui + win32clipboard."""

    # -- type_text: ASCII path ------------------------------------------------

    def test_type_text_ascii_calls_typewrite(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.type_text("hello")
        pg.typewrite.assert_called_once_with("hello", interval=0.05)

    def test_type_text_ascii_respects_custom_interval(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.type_text("abc", interval=0.1)
        pg.typewrite.assert_called_once_with("abc", interval=0.1)

    def test_type_text_ascii_default_interval_is_0_05(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.type_text("xyz")
        _, kwargs = pg.typewrite.call_args
        self.assertAlmostEqual(kwargs["interval"], 0.05)

    def test_type_text_empty_string_calls_typewrite(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.type_text("")
        pg.typewrite.assert_called_once_with("", interval=0.05)

    # -- type_text: Unicode / clipboard path ----------------------------------

    def test_type_text_unicode_uses_win32clipboard(self):
        pg = _pyautogui_mock()
        cb = _win32clipboard_mock()
        with patch.dict("sys.modules", {"pyautogui": pg, "win32clipboard": cb}):
            inp.type_text("héllo")
        cb.OpenClipboard.assert_called_once()
        cb.EmptyClipboard.assert_called_once()
        cb.SetClipboardData.assert_called_once_with(cb.CF_UNICODETEXT, "héllo")
        cb.CloseClipboard.assert_called_once()
        pg.hotkey.assert_called_once_with("ctrl", "v")

    def test_type_text_emoji_uses_clipboard_not_typewrite(self):
        pg = _pyautogui_mock()
        cb = _win32clipboard_mock()
        with patch.dict("sys.modules", {"pyautogui": pg, "win32clipboard": cb}):
            inp.type_text("hi 🎉")
        pg.typewrite.assert_not_called()
        pg.hotkey.assert_called_once_with("ctrl", "v")

    def test_type_text_non_latin_uses_clipboard(self):
        pg = _pyautogui_mock()
        cb = _win32clipboard_mock()
        with patch.dict("sys.modules", {"pyautogui": pg, "win32clipboard": cb}):
            inp.type_text("日本語")
        cb.SetClipboardData.assert_called_once_with(cb.CF_UNICODETEXT, "日本語")

    def test_type_text_unicode_closes_clipboard_on_set_error(self):
        """CloseClipboard must be called even when SetClipboardData raises."""
        pg = _pyautogui_mock()
        cb = _win32clipboard_mock()
        cb.SetClipboardData.side_effect = OSError("clipboard error")
        with patch.dict("sys.modules", {"pyautogui": pg, "win32clipboard": cb}):
            with self.assertRaises(OSError):
                inp.type_text("é")
        cb.CloseClipboard.assert_called_once()

    # -- type_text: win32clipboard absent, pyperclip fallback -----------------

    def test_type_text_falls_back_to_pyperclip_when_no_win32clipboard(self):
        pg = _pyautogui_mock()
        pyperclip = MagicMock()
        # Remove win32clipboard from sys.modules to simulate absence
        patched = {k: v for k, v in sys.modules.items() if k != "win32clipboard"}
        win32clipboard_absent = MagicMock(side_effect=ImportError)
        with patch.dict("sys.modules", {"pyautogui": pg, "pyperclip": pyperclip}), \
             patch.object(inp, "_clipboard_paste", wraps=lambda text: (
                 pyperclip.copy(text),
                 pg.hotkey("ctrl", "v"),
             )):
            # Re-test via _has_non_ascii + direct _clipboard_paste patch
            pass

        # Direct unit test of _clipboard_paste with win32clipboard missing
        pg2 = _pyautogui_mock()
        pyperclip2 = MagicMock()
        fake_win32 = types.ModuleType("win32clipboard")
        # Make the import inside _clipboard_paste raise ImportError
        with patch.dict("sys.modules", {
            "pyautogui": pg2,
            "pyperclip": pyperclip2,
            "win32clipboard": None,  # None in sys.modules triggers ImportError on import
        }):
            inp._clipboard_paste("café")
        pyperclip2.copy.assert_called_once_with("café")
        pg2.hotkey.assert_called_with("ctrl", "v")

    # -- hotkey ---------------------------------------------------------------

    def test_hotkey_calls_pyautogui_hotkey(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.hotkey("ctrl", "c")
        pg.hotkey.assert_called_once_with("ctrl", "c")

    def test_hotkey_variable_length_key_sequence(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.hotkey("ctrl", "shift", "s")
        pg.hotkey.assert_called_once_with("ctrl", "shift", "s")

    def test_hotkey_single_key(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.hotkey("alt")
        pg.hotkey.assert_called_once_with("alt")

    def test_hotkey_ctrl_v_paste(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.hotkey("ctrl", "v")
        pg.hotkey.assert_called_once_with("ctrl", "v")

    def test_hotkey_ctrl_c_copy(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.hotkey("ctrl", "c")
        pg.hotkey.assert_called_once_with("ctrl", "c")

    # -- press_key ------------------------------------------------------------

    def test_press_key_enter(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.press_key("enter")
        pg.press.assert_called_once_with("enter")

    def test_press_key_f5(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.press_key("f5")
        pg.press.assert_called_once_with("f5")

    def test_press_key_escape(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.press_key("escape")
        pg.press.assert_called_once_with("escape")

    def test_press_key_tab(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.press_key("tab")
        pg.press.assert_called_once_with("tab")

    def test_press_key_single_letter(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}):
            inp.press_key("w")
        pg.press.assert_called_once_with("w")

    # -- clear_text -----------------------------------------------------------

    def test_clear_text_calls_ctrl_a_then_delete(self):
        pg = _pyautogui_mock()
        with patch.dict("sys.modules", {"pyautogui": pg}), \
             patch("time.sleep"):
            inp.clear_text()
        pg.hotkey.assert_called_once_with("ctrl", "a")
        pg.press.assert_called_once_with("delete")

    def test_clear_text_hotkey_before_press(self):
        """ctrl+a must precede delete — verify call order."""
        pg = _pyautogui_mock()
        call_order = []
        pg.hotkey.side_effect = lambda *k: call_order.append(("hotkey", k))
        pg.press.side_effect = lambda k: call_order.append(("press", k))
        with patch.dict("sys.modules", {"pyautogui": pg}), \
             patch("time.sleep"):
            inp.clear_text()
        self.assertEqual(call_order[0], ("hotkey", ("ctrl", "a")))
        self.assertEqual(call_order[1], ("press", "delete"))

    # -- remote delegation ----------------------------------------------------

    def test_type_text_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={})
        mock_conn = MagicMock()
        mock_conn.is_local.return_value = False
        mock_conn.post = mock_post
        with patch.dict("sys.modules", {"phone_agent.windows.connection": mock_conn}):
            # Re-import to pick up patched connection
            import importlib
            mod = importlib.import_module("phone_agent.windows.input")
            with patch.object(mod, "is_local", return_value=False), \
                 patch.object(mod, "post", mock_post):
                mod.type_text("hello", device_id="192.168.1.10")
        mock_post.assert_called_once_with("192.168.1.10", "/api/action/type",
                                          {"text": "hello", "interval": 0.05})

    def test_hotkey_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={})
        import importlib
        mod = importlib.import_module("phone_agent.windows.input")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            mod.hotkey("ctrl", "shift", "s", device_id="192.168.1.10")
        mock_post.assert_called_once_with(
            "192.168.1.10", "/api/action/hotkey", {"keys": ["ctrl", "shift", "s"]}
        )

    def test_press_key_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={})
        import importlib
        mod = importlib.import_module("phone_agent.windows.input")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            mod.press_key("enter", device_id="192.168.1.10")
        mock_post.assert_called_once_with(
            "192.168.1.10", "/api/action/press_key", {"key": "enter"}
        )

    def test_clear_text_remote_posts_to_was(self):
        mock_post = MagicMock(return_value={})
        import importlib
        mod = importlib.import_module("phone_agent.windows.input")
        with patch.object(mod, "is_local", return_value=False), \
             patch.object(mod, "post", mock_post):
            mod.clear_text(device_id="192.168.1.10")
        mock_post.assert_called_once_with(
            "192.168.1.10", "/api/action/clear_text", {}
        )


# ── Integration tests (Windows-only) ─────────────────────────────────────────

_ON_WINDOWS    = platform.system() == "Windows"
_HAS_PYAUTOGUI = False
_HAS_WIN32     = False

if _ON_WINDOWS:
    try:
        import pyautogui as _pg          # noqa: F401
        _HAS_PYAUTOGUI = True
    except ImportError:
        pass
    try:
        import win32clipboard as _wc     # noqa: F401
        import win32gui as _wg           # noqa: F401
        _HAS_WIN32 = True
    except ImportError:
        pass

_SKIP = not (_ON_WINDOWS and _HAS_PYAUTOGUI and _HAS_WIN32)
_WHY = (
    f"Requires Windows + pyautogui + pywin32 "
    f"(Windows={_ON_WINDOWS}, pyautogui={_HAS_PYAUTOGUI}, win32={_HAS_WIN32})"
)


@unittest.skipIf(_SKIP, _WHY)
class IntegrationInputTests(unittest.TestCase):
    """Live keyboard input tests.  Runs only on Windows with dependencies.

    Safety constraints
    ------------------
    - Notepad is opened at start of class and killed after all tests.
    - pyautogui.FAILSAFE is kept True.
    - All timing waits give Notepad enough time to process input.
    """

    _proc: subprocess.Popen | None = None

    @classmethod
    def setUpClass(cls):
        import pyautogui
        pyautogui.FAILSAFE = True
        cls._proc = subprocess.Popen(["notepad.exe"])
        cls._wait_for_notepad()
        time.sleep(0.4)  # let Notepad fully render and take focus

    @classmethod
    def tearDownClass(cls):
        if cls._proc is not None:
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

    def _focus_notepad(self) -> None:
        """Bring Notepad to foreground."""
        import win32gui
        handles = []
        def _cb(h, _):
            if win32gui.IsWindowVisible(h) and "Notepad" in win32gui.GetWindowText(h):
                handles.append(h)
        win32gui.EnumWindows(_cb, None)
        if handles:
            win32gui.SetForegroundWindow(handles[0])
            time.sleep(0.2)

    def _get_notepad_text(self) -> str:
        """Select all text in Notepad and read via clipboard."""
        import pyautogui
        import win32clipboard
        self._focus_notepad()
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return data

    def _clear_notepad(self) -> None:
        self._focus_notepad()
        inp.clear_text()
        time.sleep(0.15)

    # -- type_text: ASCII -----------------------------------------------------

    def test_type_text_ascii_produces_expected_string(self):
        """type_text with an ASCII string should appear verbatim in Notepad."""
        self._clear_notepad()
        self._focus_notepad()
        test_str = "Hello ClawGUI"
        inp.type_text(test_str)
        time.sleep(0.3)
        result = self._get_notepad_text()
        self.assertEqual(result.strip(), test_str)

    def test_type_text_numbers_and_symbols(self):
        self._clear_notepad()
        self._focus_notepad()
        test_str = "abc123!@#"
        inp.type_text(test_str)
        time.sleep(0.3)
        result = self._get_notepad_text()
        self.assertEqual(result.strip(), test_str)

    # -- type_text: Unicode / clipboard fallback ------------------------------

    def test_type_text_unicode_produces_expected_string(self):
        """Unicode text (non-ASCII) should reach Notepad via clipboard fallback."""
        self._clear_notepad()
        self._focus_notepad()
        test_str = "Héllo Wörld"
        inp.type_text(test_str)
        time.sleep(0.3)
        result = self._get_notepad_text()
        self.assertEqual(result.strip(), test_str)

    def test_type_text_emoji_appears_in_notepad(self):
        self._clear_notepad()
        self._focus_notepad()
        test_str = "hi 🎉"
        inp.type_text(test_str)
        time.sleep(0.3)
        result = self._get_notepad_text()
        self.assertEqual(result.strip(), test_str)

    # -- clear_text -----------------------------------------------------------

    def test_clear_text_empties_the_field(self):
        """After typing and then calling clear_text, the field should be empty."""
        self._focus_notepad()
        inp.type_text("some text to clear")
        time.sleep(0.3)
        inp.clear_text()
        time.sleep(0.2)
        result = self._get_notepad_text()
        self.assertEqual(result.strip(), "")

    # -- hotkey ---------------------------------------------------------------

    def test_hotkey_ctrl_a_selects_text(self):
        """hotkey('ctrl','a') should select all text — verifiable via clipboard."""
        self._clear_notepad()
        self._focus_notepad()
        inp.type_text("select me")
        time.sleep(0.2)
        inp.hotkey("ctrl", "a")
        time.sleep(0.1)
        import pyautogui
        import win32clipboard
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        self.assertEqual(data.strip(), "select me")

    # -- press_key ------------------------------------------------------------

    def test_press_key_enter_adds_newline(self):
        self._clear_notepad()
        self._focus_notepad()
        inp.type_text("line1")
        inp.press_key("enter")
        inp.type_text("line2")
        time.sleep(0.3)
        result = self._get_notepad_text()
        self.assertIn("line1", result)
        self.assertIn("line2", result)
        self.assertIn("\n", result)

    def test_press_key_escape_executes_without_exception(self):
        inp.press_key("escape")  # should not raise

    def test_press_key_tab_executes_without_exception(self):
        self._focus_notepad()
        inp.press_key("tab")  # should not raise


if __name__ == "__main__":
    unittest.main()
