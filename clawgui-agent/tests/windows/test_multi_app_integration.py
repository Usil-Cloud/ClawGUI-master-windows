"""Multi-app integration tests spanning Notepad, Paint, and VS Code.

Covers both Feature 1-C (keyboard input) and Feature 1-D (window manager) to
verify that all primitives work across diverse application types.

App lifecycle
-------------
setUpModule opens all three apps once.  tearDownModule closes them:
  - Notepad / Paint: killed via Popen.kill()
  - VS Code: WM_CLOSE sent to the specific hwnd we captured at startup so that
    any other VS Code windows the user has open are untouched, followed by a
    process kill if the launcher is still alive.

Test classes
------------
MultiAppWindowTests   — list_windows / focus_window across Notepad, Paint,
                        and VS Code (Feature 1-D).
MultiAppKeyboardTests — type_text / hotkey / press_key / clear_text across
                        Notepad, Paint, and VS Code (Feature 1-C).

Run all:
    python -m pytest tests/windows/test_multi_app_integration.py -v

Run only window tests:
    python -m pytest tests/windows/test_multi_app_integration.py -v -k "Window"

Run only keyboard tests:
    python -m pytest tests/windows/test_multi_app_integration.py -v -k "Keyboard"
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Pre-stub heavy optional deps so phone_agent imports succeed on any OS.
# _stub_if_missing() only installs a stub when the real package is absent,
# so on Windows with pywin32 installed the real modules are used.
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
    GetWindowText=lambda h: "",
    EnumWindows=lambda cb, x: None,
    GetWindowRect=lambda h: (0, 0, 800, 600),
    SetForegroundWindow=lambda h: None,
    GetForegroundWindow=lambda: 0,
    IsIconic=lambda h: False,
    ShowWindow=lambda h, cmd: None,
    PostMessage=lambda h, msg, w, l: None,
    GetWindowPlacement=lambda h: (0, 1, 0, (0, 0), (0, 0, 800, 600)),
)
_stub_if_missing("win32con",
    SW_MINIMIZE=6, SW_MAXIMIZE=3, SW_RESTORE=9,
    SW_SHOWMAXIMIZED=3,
    WM_CLOSE=0x0010, SC_CLOSE=0xF060,
)
_stub_if_missing("win32clipboard",
    OpenClipboard=lambda: None,
    CloseClipboard=lambda: None,
    EmptyClipboard=lambda: None,
    SetClipboardData=lambda fmt, data: None,
    GetClipboardData=lambda fmt: "",
    IsClipboardFormatAvailable=lambda fmt: False,
    CF_UNICODETEXT=13,
)
_stub_if_missing("pyautogui",
    hotkey=lambda *keys: None,
    press=lambda key: None,
    typewrite=lambda text, interval=0.05: None,
    click=lambda x, y: None,
    FAILSAFE=True,
)
_stub_if_missing("mss", mss=MagicMock)
_stub_if_missing("PIL.Image")
_stub_if_missing("phone_agent.windows.connection",
    is_local=lambda device_id: True,
    post=lambda *a, **kw: {},
    ConnectionMode=object,
    DeviceInfo=object,
    WindowsConnection=object,
    verify_connection=lambda *a, **kw: True,
    list_devices=lambda: [],
)
_stub_if_missing("phone_agent.config.apps_windows", APP_PACKAGES_WINDOWS={})
_stub_if_missing("openai", OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent", PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios", IOSPhoneAgent=MagicMock)

# ---------------------------------------------------------------------------
# Runtime capability checks — must run BEFORE stubs so we detect real modules
# ---------------------------------------------------------------------------

_ON_WINDOWS    = platform.system() == "Windows"
_HAS_WIN32     = False
_HAS_PYAUTOGUI = False
_HAS_VSCODE    = bool(shutil.which("code"))

if _ON_WINDOWS:
    try:
        import importlib
        importlib.import_module("win32gui")
        importlib.import_module("win32con")
        importlib.import_module("win32clipboard")
        _HAS_WIN32 = True
    except ImportError:
        pass
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        _HAS_PYAUTOGUI = True
    except ImportError:
        pass

import phone_agent.windows.window_manager as wm_mod  # noqa: E402
import phone_agent.windows.input as inp_mod           # noqa: E402

_WIN_SKIP = not (_ON_WINDOWS and _HAS_WIN32)
_WIN_WHY  = (
    f"Requires Windows + pywin32 "
    f"(Windows={_ON_WINDOWS}, win32={_HAS_WIN32})"
)
_KB_SKIP  = not (_ON_WINDOWS and _HAS_WIN32 and _HAS_PYAUTOGUI)
_KB_WHY   = (
    f"Requires Windows + pywin32 + pyautogui "
    f"(Windows={_ON_WINDOWS}, win32={_HAS_WIN32}, pyautogui={_HAS_PYAUTOGUI})"
)

# ---------------------------------------------------------------------------
# Module-level app fixture — opened once, shared by both test classes
# ---------------------------------------------------------------------------

_notepad_proc: subprocess.Popen | None = None
_paint_proc:   subprocess.Popen | None = None
_vscode_proc:  subprocess.Popen | None = None
_vscode_hwnd:  int | None = None


def _wait_for_window(partial_title: str, timeout: float = 10.0) -> int:
    """Poll until a visible window matching partial_title appears; return hwnd."""
    import win32gui
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found: list[int] = []
        def _cb(h, _):
            if win32gui.IsWindowVisible(h) and partial_title.lower() in win32gui.GetWindowText(h).lower():
                found.append(h)
        win32gui.EnumWindows(_cb, None)
        if found:
            return found[0]
        time.sleep(0.15)
    raise RuntimeError(f"Window {partial_title!r} did not appear within {timeout}s")


def _clear_clipboard() -> None:
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
    finally:
        win32clipboard.CloseClipboard()


def _read_clipboard() -> str:
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return ""
    finally:
        win32clipboard.CloseClipboard()


def setUpModule():  # noqa: N802
    global _notepad_proc, _paint_proc, _vscode_proc, _vscode_hwnd
    if not (_ON_WINDOWS and _HAS_WIN32):
        return

    _notepad_proc = subprocess.Popen(["notepad.exe"])
    _paint_proc   = subprocess.Popen(["mspaint.exe"])
    time.sleep(1.5)  # Windows 11 Store apps need a head-start before polling
    _wait_for_window("Notepad", timeout=15)
    _wait_for_window("Paint",   timeout=15)

    if _HAS_VSCODE:
        _vscode_proc = subprocess.Popen(["code", "--new-window"])
        _vscode_hwnd = _wait_for_window("Visual Studio Code", timeout=15)

    time.sleep(0.8)  # let all apps finish rendering before tests begin


def tearDownModule():  # noqa: N802
    global _notepad_proc, _paint_proc, _vscode_proc, _vscode_hwnd
    if not (_ON_WINDOWS and _HAS_WIN32):
        return

    # Close VS Code by hwnd so unrelated VS Code windows are not affected
    if _vscode_hwnd:
        try:
            import win32gui, win32con
            win32gui.PostMessage(_vscode_hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(0.6)
        except Exception:
            pass
    if _vscode_proc and _vscode_proc.poll() is None:
        _vscode_proc.kill()
        _vscode_proc.wait(timeout=5)

    for proc in [_notepad_proc, _paint_proc]:
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)


# ---------------------------------------------------------------------------
# Feature 1-D: Window manager across all three apps
# ---------------------------------------------------------------------------

@unittest.skipIf(_WIN_SKIP, _WIN_WHY)
class MultiAppWindowTests(unittest.TestCase):
    """list_windows / focus_window verified against Notepad, Paint, VS Code."""

    # ── list_windows ──────────────────────────────────────────────────────────

    def test_list_windows_finds_notepad(self):
        result = wm_mod.list_windows()
        titles = [w.title for w in result]
        self.assertTrue(any("Notepad" in t for t in titles),
                        f"Notepad not found; got: {titles}")

    def test_list_windows_finds_paint(self):
        result = wm_mod.list_windows()
        titles = [w.title for w in result]
        self.assertTrue(any("Paint" in t for t in titles),
                        f"Paint not found; got: {titles}")

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_list_windows_finds_vscode(self):
        result = wm_mod.list_windows()
        titles = [w.title for w in result]
        self.assertTrue(any("Visual Studio Code" in t for t in titles),
                        f"VS Code not found; got: {titles}")

    def test_list_windows_all_entries_are_visible(self):
        for w in wm_mod.list_windows():
            self.assertTrue(w.visible, f"{w.title!r} flagged as not visible")

    def test_list_windows_all_entries_have_nonempty_titles(self):
        for w in wm_mod.list_windows():
            self.assertTrue(w.title, f"hwnd={w.hwnd} has an empty title")

    def test_list_windows_notepad_has_positive_hwnd(self):
        result = wm_mod.list_windows()
        notepad = next((w for w in result if "Notepad" in w.title), None)
        self.assertIsNotNone(notepad, "Notepad not found in list_windows()")
        self.assertGreater(notepad.hwnd, 0)

    def test_list_windows_paint_has_positive_hwnd(self):
        result = wm_mod.list_windows()
        paint = next((w for w in result if "Paint" in w.title), None)
        self.assertIsNotNone(paint, "Paint not found in list_windows()")
        self.assertGreater(paint.hwnd, 0)

    def test_list_windows_notepad_rect_is_4_tuple(self):
        result = wm_mod.list_windows()
        notepad = next((w for w in result if "Notepad" in w.title), None)
        self.assertIsNotNone(notepad)
        self.assertIsInstance(notepad.rect, tuple)
        self.assertEqual(len(notepad.rect), 4)

    def test_list_windows_paint_rect_is_4_tuple(self):
        result = wm_mod.list_windows()
        paint = next((w for w in result if "Paint" in w.title), None)
        self.assertIsNotNone(paint)
        self.assertIsInstance(paint.rect, tuple)
        self.assertEqual(len(paint.rect), 4)

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_list_windows_vscode_rect_is_4_tuple(self):
        result = wm_mod.list_windows()
        vscode = next((w for w in result if "Visual Studio Code" in w.title), None)
        self.assertIsNotNone(vscode, "VS Code not found in list_windows()")
        self.assertIsInstance(vscode.rect, tuple)
        self.assertEqual(len(vscode.rect), 4)

    def test_list_windows_notepad_and_paint_have_different_hwnds(self):
        result  = wm_mod.list_windows()
        notepad = next((w for w in result if "Notepad" in w.title), None)
        paint   = next((w for w in result if "Paint"   in w.title), None)
        self.assertIsNotNone(notepad)
        self.assertIsNotNone(paint)
        self.assertNotEqual(notepad.hwnd, paint.hwnd)

    # ── focus_window ──────────────────────────────────────────────────────────

    def test_focus_window_notepad_exact_returns_true(self):
        self.assertTrue(wm_mod.focus_window("Notepad"))
        time.sleep(0.3)

    def test_focus_window_notepad_partial_lowercase_returns_true(self):
        self.assertTrue(wm_mod.focus_window("note"))
        time.sleep(0.3)

    def test_focus_window_notepad_brings_to_foreground(self):
        import win32gui
        wm_mod.focus_window("Notepad")
        time.sleep(0.3)
        fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        self.assertIn("Notepad", fg, f"Foreground after focus is {fg!r}")

    def test_focus_window_paint_exact_returns_true(self):
        self.assertTrue(wm_mod.focus_window("Paint"))
        time.sleep(0.3)

    def test_focus_window_paint_partial_lowercase_returns_true(self):
        self.assertTrue(wm_mod.focus_window("paint"))
        time.sleep(0.3)

    def test_focus_window_paint_brings_to_foreground(self):
        import win32gui
        wm_mod.focus_window("Paint")
        time.sleep(0.3)
        fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        self.assertIn("Paint", fg, f"Foreground after focus is {fg!r}")

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_focus_window_vscode_partial_returns_true(self):
        self.assertTrue(wm_mod.focus_window("Visual Studio Code"))
        time.sleep(0.3)

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_focus_window_vscode_lowercase_partial_returns_true(self):
        self.assertTrue(wm_mod.focus_window("visual studio"))
        time.sleep(0.3)

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_focus_window_vscode_brings_to_foreground(self):
        import win32gui
        wm_mod.focus_window("Visual Studio Code")
        time.sleep(0.4)
        fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        self.assertIn("Visual Studio Code", fg, f"Foreground after focus is {fg!r}")

    def test_focus_window_cycles_notepad_then_paint(self):
        """Cycle Notepad → Paint and verify foreground title changes each time."""
        import win32gui
        for title, keyword in [("Notepad", "Notepad"), ("Paint", "Paint")]:
            ok = wm_mod.focus_window(title)
            time.sleep(0.35)
            self.assertTrue(ok, f"focus_window({title!r}) returned False")
            fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            self.assertIn(keyword, fg,
                          f"After focus_window({title!r}), foreground is {fg!r}")

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_focus_window_cycles_all_three_apps(self):
        """Cycle Notepad → Paint → VS Code and confirm each comes to front."""
        import win32gui
        targets = [
            ("Notepad",            "Notepad"),
            ("Paint",              "Paint"),
            ("Visual Studio Code", "Visual Studio Code"),
        ]
        for title, keyword in targets:
            ok = wm_mod.focus_window(title)
            time.sleep(0.4)
            self.assertTrue(ok, f"focus_window({title!r}) returned False")
            fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            self.assertIn(keyword, fg,
                          f"After focus_window({title!r}), foreground is {fg!r}")

    def test_focus_window_nonexistent_returns_false(self):
        self.assertFalse(wm_mod.focus_window("nonexistent_xyz_not_a_real_window"))

    def test_focus_window_nonexistent_does_not_raise(self):
        try:
            wm_mod.focus_window("nonexistent_xyz")
        except Exception as exc:
            self.fail(f"focus_window raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Feature 1-C: Keyboard input across Notepad, Paint, VS Code
# ---------------------------------------------------------------------------

@unittest.skipIf(_KB_SKIP, _KB_WHY)
class MultiAppKeyboardTests(unittest.TestCase):
    """type_text / hotkey / press_key / clear_text across all three apps."""

    # ── helpers ───────────────────────────────────────────────────────────────

    def _focus(self, partial_title: str) -> None:
        wm_mod.focus_window(partial_title)
        time.sleep(0.3)

    def _get_notepad_text(self) -> str:
        import pyautogui
        self._focus("Notepad")
        _clear_clipboard()
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        return _read_clipboard()

    def _clear_notepad(self) -> None:
        self._focus("Notepad")
        inp_mod.clear_text()
        time.sleep(0.2)

    # ── Notepad ───────────────────────────────────────────────────────────────

    def test_type_text_ascii_in_notepad(self):
        self._clear_notepad()
        self._focus("Notepad")
        inp_mod.type_text("Hello ClawGUI")
        time.sleep(0.3)
        self.assertEqual(self._get_notepad_text().strip(), "Hello ClawGUI")

    def test_type_text_numbers_and_symbols_in_notepad(self):
        self._clear_notepad()
        self._focus("Notepad")
        inp_mod.type_text("test123!@#")
        time.sleep(0.3)
        self.assertEqual(self._get_notepad_text().strip(), "test123!@#")

    def test_type_text_unicode_in_notepad(self):
        self._clear_notepad()
        self._focus("Notepad")
        inp_mod.type_text("Héllo Wörld")
        time.sleep(0.3)
        self.assertEqual(self._get_notepad_text().strip(), "Héllo Wörld")

    def test_press_key_enter_creates_newline_in_notepad(self):
        self._clear_notepad()
        self._focus("Notepad")
        inp_mod.type_text("line1")
        inp_mod.press_key("enter")
        inp_mod.type_text("line2")
        time.sleep(0.3)
        result = self._get_notepad_text()
        self.assertIn("line1", result)
        self.assertIn("line2", result)
        self.assertIn("\n", result)

    def test_clear_text_empties_notepad(self):
        self._focus("Notepad")
        inp_mod.type_text("text to be cleared")
        time.sleep(0.2)
        _clear_clipboard()
        self._clear_notepad()
        self.assertEqual(self._get_notepad_text().strip(), "")

    def test_hotkey_ctrl_a_selects_all_in_notepad(self):
        import pyautogui
        self._clear_notepad()
        self._focus("Notepad")
        inp_mod.type_text("select all test")
        time.sleep(0.2)
        inp_mod.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        self.assertEqual(_read_clipboard().strip(), "select all test")

    # ── Paint (keyboard smoke tests) ──────────────────────────────────────────

    def test_hotkey_ctrl_z_undo_in_paint_does_not_raise(self):
        """Ctrl+Z (undo) in Paint must not raise."""
        self._focus("Paint")
        try:
            inp_mod.hotkey("ctrl", "z")
            time.sleep(0.2)
        except Exception as exc:
            self.fail(f"hotkey Ctrl+Z in Paint raised: {exc}")

    def test_press_key_escape_in_paint_does_not_raise(self):
        """Escape in Paint must not raise."""
        self._focus("Paint")
        try:
            inp_mod.press_key("escape")
            time.sleep(0.1)
        except Exception as exc:
            self.fail(f"press_key(escape) in Paint raised: {exc}")

    def test_type_text_in_paint_text_tool_does_not_raise(self):
        """Activate Paint text tool via keyboard, click canvas, type — must not raise."""
        import pyautogui
        self._focus("Paint")
        time.sleep(0.2)
        # Get Paint window rect to click the canvas center
        result = wm_mod.list_windows()
        paint_win = next((w for w in result if "Paint" in w.title), None)
        if paint_win is None:
            self.skipTest("Paint window not found in list_windows()")
        left, top, right, bottom = paint_win.rect
        canvas_x = (left + right)  // 2
        canvas_y = (top  + bottom) // 2 + 40  # offset below ribbon
        try:
            pyautogui.press("t")          # activate text tool
            time.sleep(0.2)
            pyautogui.click(canvas_x, canvas_y)
            time.sleep(0.3)
            inp_mod.type_text("ClawGUI")
            time.sleep(0.2)
            inp_mod.press_key("escape")   # exit text tool
        except Exception as exc:
            self.fail(f"type_text in Paint text tool raised: {exc}")

    # ── VS Code ───────────────────────────────────────────────────────────────

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_type_text_ascii_in_vscode_new_file(self):
        """Open a new untitled file in VS Code, type ASCII text, verify via
        clipboard.  The file is left open; tearDownModule closes VS Code."""
        import pyautogui
        self._focus("Visual Studio Code")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "n")  # new untitled file
        time.sleep(1.2)                 # wait for editor tab to open
        test_str = "ClawGUI VSCode Test"
        inp_mod.type_text(test_str)
        time.sleep(0.3)
        _clear_clipboard()
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        self.assertEqual(_read_clipboard().strip(), test_str)

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_hotkey_opens_command_palette_in_vscode(self):
        """Ctrl+Shift+P must open the VS Code command palette without raising."""
        self._focus("Visual Studio Code")
        time.sleep(0.2)
        try:
            inp_mod.hotkey("ctrl", "shift", "p")
            time.sleep(0.4)
            inp_mod.press_key("escape")   # dismiss palette
            time.sleep(0.2)
        except Exception as exc:
            self.fail(f"Command palette hotkey raised: {exc}")

    @unittest.skipIf(not _HAS_VSCODE, "VS Code not in PATH")
    def test_press_key_escape_dismisses_vscode_palette(self):
        """Escape after opening the command palette must close it without raising."""
        import pyautogui
        self._focus("Visual Studio Code")
        pyautogui.hotkey("ctrl", "shift", "p")
        time.sleep(0.4)
        try:
            inp_mod.press_key("escape")
        except Exception as exc:
            self.fail(f"press_key(escape) in VS Code raised: {exc}")


if __name__ == "__main__":
    unittest.main()
