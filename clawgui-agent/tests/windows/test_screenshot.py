"""Tests for phone_agent/windows/screenshot.py -- Feature 1-A.

Test structure
--------------
Unit tests (MockedScreenshotTests)
    Patch sys.modules so lazy "import mss" / "import win32gui" calls inside
    the production functions pick up mocks automatically.  Runs on any OS.

Integration tests (IntegrationScreenshotTests)
    Require a real Windows machine with mss + pywin32 installed.
    Skipped automatically on non-Windows or when dependencies are absent.
    setUpClass opens Notepad via subprocess.Popen; tearDownClass kills it.

Run all tests:
    pytest tests/windows/test_screenshot.py -v

Run only unit tests (safe on any OS):
    pytest tests/windows/test_screenshot.py -v -k "not Integration"
"""
# Notes: docs/tests/windows/test_screenshot.md
from __future__ import annotations

import base64
import platform
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Pre-stub heavy optional deps so the module-level import of screenshot.py
# succeeds on non-Windows machines that lack mss / win32gui.
# ---------------------------------------------------------------------------

def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _stub_if_missing(name: str, **attrs) -> None:
    """Install a stub only when the real module cannot be imported.

    Uses setdefault so a previously imported real module is never evicted.
    On Windows with pywin32 installed, win32gui won't be in sys.modules yet
    at test-file import time, so we probe with __import__ first.
    """
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
    GetWindowRect=lambda h: (0, 0, 1920, 1080),
)
_stub_if_missing("win32ui")
_stub_if_missing("win32con", SRCCOPY=0xCC0020)
_stub_if_missing("pywintypes")

# Stub connection so is_local / post resolve without the full package.
_stub_if_missing("phone_agent.windows.connection",
    is_local=lambda device_id: True,
    post=lambda *a, **kw: {},
    ConnectionMode=object,
    DeviceInfo=object,
    WindowsConnection=object,
    verify_connection=lambda *a, **kw: True,
    list_devices=lambda: [],
)

from phone_agent.windows import screenshot as sc  # noqa: E402


# ── mock builders ────────────────────────────────────────────────────────────

def _mss_modules(w: int, h: int, primary_w: int = 1920, primary_h: int = 1080):
    """Return (mss_mod, mss_tools_mod, sct_inner) ready for sys.modules patching.

    sct_inner.grab() returns a fake image of size (w, h).
    sct_inner.monitors[1] reports (primary_w, primary_h).
    """
    img = MagicMock()
    img.width  = w
    img.height = h
    img.rgb    = b"\x00" * (w * h * 3)
    img.size   = (w, h)

    sct_inner = MagicMock()
    sct_inner.monitors = [
        {},                                                          # [0] all-screens
        {"left": 0, "top": 0, "width": primary_w, "height": primary_h},  # [1] primary
    ]
    sct_inner.grab.return_value = img

    ctx_mgr = MagicMock()
    ctx_mgr.__enter__ = MagicMock(return_value=sct_inner)
    ctx_mgr.__exit__  = MagicMock(return_value=False)

    mss_mod = MagicMock()
    mss_mod.mss.return_value = ctx_mgr

    mss_tools = MagicMock()
    mss_tools.to_png = lambda rgb, size: b"\x89PNG" + b"\x00" * 20
    mss_mod.tools = mss_tools

    return mss_mod, mss_tools, sct_inner


def _win32gui_mock(hwnd: int | None, rect=(100, 100, 900, 700)):
    """Return a win32gui mock wired to a given HWND and window rect."""
    w32 = MagicMock()
    w32.IsWindowVisible.return_value = hwnd is not None
    w32.GetWindowText.return_value   = "Mocked Window" if hwnd else ""
    w32.GetWindowRect.return_value   = rect

    def _enum(cb, _):
        if hwnd is not None:
            cb(hwnd, None)
    w32.EnumWindows.side_effect = _enum
    return w32


# ── Unit tests ───────────────────────────────────────────────────────────────

class MockedScreenshotTests(unittest.TestCase):
    """Four auto-mode scenarios + edge cases, all via sys.modules patching."""

    SCREEN_W  = 1920
    SCREEN_H  = 1080
    WIN_W     = 800
    WIN_H     = 600
    FAKE_HWND = 12345

    # -- helpers --------------------------------------------------------------

    def _sys_modules_patch(self, mss_w=None, mss_h=None):
        """Patch sys.modules so lazy 'import mss' / 'import mss.tools' hit our mock."""
        w = mss_w or self.WIN_W
        h = mss_h or self.WIN_H
        mss_mod, mss_tools, sct = _mss_modules(w, h, self.SCREEN_W, self.SCREEN_H)
        return (
            patch.dict("sys.modules", {"mss": mss_mod, "mss.tools": mss_tools}),
            mss_mod, sct,
        )

    # -- Scenario 1: focus_apps window IS open --------------------------------

    def test_found_window_returns_window_mode(self):
        """Single focus_apps entry, window found -> mode='window', sized like the window."""
        mss_p, mss_mod, sct = self._sys_modules_patch(self.WIN_W, self.WIN_H)
        w32 = _win32gui_mock(self.FAKE_HWND,
                             rect=(100, 100, 100 + self.WIN_W, 100 + self.WIN_H))

        with mss_p,              patch.dict("sys.modules", {"win32gui": w32}),              patch("phone_agent.windows.screenshot._find_window",
                   return_value=self.FAKE_HWND):
            shot = sc.get_screenshot(focus_apps=["Notepad"])

        self.assertEqual(shot.mode, "window")
        self.assertEqual(shot.width,  self.WIN_W)
        self.assertEqual(shot.height, self.WIN_H)
        self.assertIsInstance(shot.base64_data, str)
        self.assertGreater(len(shot.base64_data), 0)

    # -- Scenario 2: focus_apps window NOT open -------------------------------

    def test_not_found_window_falls_back_to_full_no_exception(self):
        """Window NOT found -> mode='full', no exception raised."""
        mss_p, mss_mod, sct = self._sys_modules_patch(self.SCREEN_W, self.SCREEN_H)
        sct.grab.return_value.width  = self.SCREEN_W
        sct.grab.return_value.height = self.SCREEN_H

        with mss_p,              patch("phone_agent.windows.screenshot._find_window", return_value=None):
            shot = sc.get_screenshot(focus_apps=["Blender"])

        self.assertEqual(shot.mode, "full")
        self.assertEqual(shot.width,  self.SCREEN_W)
        self.assertEqual(shot.height, self.SCREEN_H)

    def test_not_found_window_mid_launch_no_exception(self):
        """Mid-launch scenario: window not yet visible -> graceful fallback."""
        mss_p, mss_mod, sct = self._sys_modules_patch(self.SCREEN_W, self.SCREEN_H)
        sct.grab.return_value.width  = self.SCREEN_W
        sct.grab.return_value.height = self.SCREEN_H

        with mss_p,              patch("phone_agent.windows.screenshot._find_window", return_value=None):
            shot = sc.get_screenshot(focus_apps=["UnrealEditor"])

        self.assertEqual(shot.mode, "full")

    def test_minimised_window_falls_back_to_full(self):
        """Window found but minimised (zero rect) -> fallback, no exception."""
        mss_p, mss_mod, sct = self._sys_modules_patch(self.SCREEN_W, self.SCREEN_H)
        sct.grab.return_value.width  = self.SCREEN_W
        sct.grab.return_value.height = self.SCREEN_H

        w32 = _win32gui_mock(self.FAKE_HWND, rect=(0, 0, 0, 0))  # zero size
        with mss_p,              patch.dict("sys.modules", {"win32gui": w32}),              patch("phone_agent.windows.screenshot._find_window",
                   return_value=self.FAKE_HWND):
            shot = sc.get_screenshot(focus_apps=["Notepad"])

        self.assertEqual(shot.mode, "full")

    # -- Scenario 3: multiple focus_apps -> full monitor ----------------------

    def test_multiple_focus_apps_returns_full_mode(self):
        """Multiple entries -> full monitor regardless of what is open."""
        mss_p, mss_mod, sct = self._sys_modules_patch(self.SCREEN_W, self.SCREEN_H)
        sct.grab.return_value.width  = self.SCREEN_W
        sct.grab.return_value.height = self.SCREEN_H

        with mss_p:
            shot = sc.get_screenshot(focus_apps=["Blender", "Chrome"])

        self.assertEqual(shot.mode, "full")
        self.assertEqual(shot.width, self.SCREEN_W)

    # -- Scenario 4: None / empty -> full monitor -----------------------------

    def test_none_focus_apps_returns_full_mode(self):
        mss_p, mss_mod, sct = self._sys_modules_patch(self.SCREEN_W, self.SCREEN_H)
        sct.grab.return_value.width  = self.SCREEN_W
        sct.grab.return_value.height = self.SCREEN_H

        with mss_p:
            shot = sc.get_screenshot(focus_apps=None)

        self.assertEqual(shot.mode, "full")

    def test_empty_list_returns_full_mode(self):
        mss_p, mss_mod, sct = self._sys_modules_patch(self.SCREEN_W, self.SCREEN_H)
        sct.grab.return_value.width  = self.SCREEN_W
        sct.grab.return_value.height = self.SCREEN_H

        with mss_p:
            shot = sc.get_screenshot(focus_apps=[])

        self.assertEqual(shot.mode, "full")

    # -- Screenshot dataclass -------------------------------------------------

    def test_screenshot_default_mode_is_full(self):
        shot = sc.Screenshot(base64_data="abc", width=1920, height=1080)
        self.assertEqual(shot.mode, "full")
        self.assertFalse(shot.is_sensitive)

    def test_screenshot_window_mode(self):
        shot = sc.Screenshot(base64_data="abc", width=800, height=600, mode="window")
        self.assertEqual(shot.mode, "window")

    # -- get_screen_size ------------------------------------------------------

    def test_get_screen_size_returns_correct_values(self):
        mss_mod, _, sct = _mss_modules(100, 100, 2560, 1440)
        with patch.dict("sys.modules", {"mss": mss_mod}):
            w, h = sc.get_screen_size()
        self.assertEqual(w, 2560)
        self.assertEqual(h, 1440)

    def test_get_screen_size_fallback_on_import_error(self):
        """If mss is unavailable, returns (1920, 1080) without crashing."""
        broken = MagicMock()
        broken.mss.side_effect = Exception("no display")
        with patch.dict("sys.modules", {"mss": broken}):
            w, h = sc.get_screen_size()
        self.assertEqual((w, h), (1920, 1080))


# ── Integration tests (Windows-only, real Notepad) ───────────────────────────

_ON_WINDOWS   = platform.system() == "Windows"
_HAS_WIN32GUI = False
_HAS_MSS      = False

if _ON_WINDOWS:
    try:
        import win32gui as _w  # noqa: F401
        _HAS_WIN32GUI = True
    except ImportError:
        pass
    try:
        import mss as _m  # noqa: F401
        _HAS_MSS = True
    except ImportError:
        pass

_SKIP = not (_ON_WINDOWS and _HAS_WIN32GUI and _HAS_MSS)
_WHY  = (
    f"Requires Windows + pywin32 + mss "
    f"(Windows={_ON_WINDOWS}, win32gui={_HAS_WIN32GUI}, mss={_HAS_MSS})"
)


@unittest.skipIf(_SKIP, _WHY)
class IntegrationScreenshotTests(unittest.TestCase):
    """Real capture tests. Runs only on Windows with dependencies installed.

    setUpClass opens Notepad so there is a known window to target.
    tearDownClass kills it, leaving no processes behind.
    """

    NOTEPAD_TITLE = "Notepad"

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
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if sc._find_window(cls.NOTEPAD_TITLE):
                    break
                time.sleep(0.1)
            else:
                cls._proc.kill()
                raise RuntimeError("Notepad did not open within 5 seconds.")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_proc", True) and cls._proc is not None:
            cls._proc.kill()
            cls._proc.wait(timeout=3)

    def _full_size(self):
        return sc.get_screen_size()

    def test_found_window_smaller_than_full_monitor(self):
        shot = sc.get_screenshot(focus_apps=[self.NOTEPAD_TITLE])
        fw, fh = self._full_size()
        self.assertEqual(shot.mode, "window")
        self.assertLess(shot.width * shot.height, fw * fh)

    def test_found_window_decodes_to_valid_png(self):
        from PIL import Image
        import io
        shot = sc.get_screenshot(focus_apps=[self.NOTEPAD_TITLE])
        img = Image.open(io.BytesIO(base64.b64decode(shot.base64_data)))
        self.assertEqual(img.format, "PNG")
        self.assertGreater(img.width * img.height, 0)

    def test_not_found_app_fallback_no_exception(self):
        shot = sc.get_screenshot(focus_apps=["__nonexistent_xyz__"])
        fw, fh = self._full_size()
        self.assertEqual(shot.mode, "full")
        self.assertEqual(shot.width,  fw)
        self.assertEqual(shot.height, fh)

    def test_multiple_focus_apps_returns_full_monitor(self):
        shot = sc.get_screenshot(focus_apps=[self.NOTEPAD_TITLE, "Explorer"])
        fw, fh = self._full_size()
        self.assertEqual(shot.mode, "full")
        self.assertEqual(shot.width, fw)

    def test_none_focus_apps_returns_full_monitor(self):
        shot = sc.get_screenshot(focus_apps=None)
        self.assertEqual(shot.mode, "full")

    def test_full_monitor_decodes_to_valid_png(self):
        from PIL import Image
        import io
        shot = sc.get_screenshot()
        img = Image.open(io.BytesIO(base64.b64decode(shot.base64_data)))
        fw, fh = self._full_size()
        self.assertEqual(img.format, "PNG")
        self.assertEqual((img.width, img.height), (fw, fh))


if __name__ == "__main__":
    unittest.main()
