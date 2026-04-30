"""Windows screenshot capture -- smart window vs full-monitor logic.

Capture modes
-------------
full   -- grabs the entire primary monitor via mss.
window -- grabs only the bounding rect of a specific window via mss.
          Falls back to full automatically when the window is not found
          (e.g. app not yet open, mid-launch, or title mismatch) so the
          agent loop never stalls waiting for a window to appear.

Why mss for window capture (not BitBlt)
----------------------------------------
BitBlt reads from the GDI device context, which returns black for any
window using Direct3D / OpenGL / GPU composition -- i.e. Blender, UE5,
Chrome, and most modern apps.  mss reads from the composited screen
buffer (via DXGI on Windows 8+), so it captures GPU-rendered content
correctly.  The only requirement is that the window is not minimised
(zero-size rect).
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from phone_agent.windows.connection import is_local, post

log = logging.getLogger(__name__)

CaptureMode = Literal["full", "window"]


@dataclass
class Screenshot:
    """Matches the ClawGUI Screenshot dataclass used by all platform modules.

    The ``mode`` field records whether this was a full-monitor or single-window
    capture so callers (GUI-Owl adapter, WAS verification envelope) can log and
    reason about it without re-inspecting dimensions.
    """

    base64_data: str
    width: int
    height: int
    mode: CaptureMode = "full"
    is_sensitive: bool = False


def get_screenshot(
    device_id: str | None = None,
    timeout: int = 10,
    focus_apps: list[str] | None = None,
) -> Screenshot:
    """Capture the screen with automatic mode selection.

    Mode selection rules
    --------------------
    - Single app in focus_apps AND window found     -> window capture (mode='window')
    - Single app in focus_apps AND window NOT found -> full monitor  (mode='full')
      No exception is raised -- the agent loop continues with a full screenshot.
    - Multiple apps in focus_apps                   -> full monitor
    - focus_apps is None or empty                   -> full monitor (safe default)

    For remote device_id the WAS /api/screenshot endpoint applies the same
    rules on the target machine and returns the result as base64 PNG.
    """
    if is_local(device_id):
        if focus_apps and len(focus_apps) == 1:
            return _capture_window_by_title(focus_apps[0])
        return _capture_full_local()

    # Remote: delegate to WAS
    window_title = focus_apps[0] if (focus_apps and len(focus_apps) == 1) else None
    data = post(
        device_id,
        "/api/screenshot",
        {"window_title": window_title or ""},
        timeout=timeout,
    )
    b64 = data["image"]
    w = data.get("width", 0)
    h = data.get("height", 0)
    if not (w and h):
        from PIL import Image
        img = Image.open(BytesIO(base64.b64decode(b64)))
        w, h = img.width, img.height
    mode: CaptureMode = "window" if window_title else "full"
    return Screenshot(base64_data=b64, width=w, height=h, mode=mode)


# -- local capture helpers ----------------------------------------------------

def _capture_full_local() -> Screenshot:
    """Grab the entire primary monitor using mss."""
    import mss
    import mss.tools

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # monitors[0] is the virtual "all screens" monitor
        img = sct.grab(monitor)
        png = mss.tools.to_png(img.rgb, img.size)
    b64 = base64.b64encode(png).decode()
    return Screenshot(base64_data=b64, width=img.width, height=img.height, mode="full")


def _capture_window_by_title(title: str) -> Screenshot:
    """Capture a window by partial title match using mss bounding-rect.

    Falls back to full-monitor capture -- without raising -- when:
    - No matching window is found (app not open or mid-launch).
    - The matching window is minimised (zero or negative bounding rect).
    - Any unexpected error occurs.

    Using mss (not BitBlt) means this works correctly for GPU-accelerated
    windows: Blender, Unreal Engine, Chrome, VS Code, etc.
    """
    hwnd = _find_window(title)

    if hwnd is None:
        log.debug("screenshot: window %r not found -- falling back to full monitor", title)
        return _capture_full_local()

    try:
        import win32gui

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w, h = right - left, bottom - top

        if w <= 0 or h <= 0:
            log.debug(
                "screenshot: window %r has zero/negative size (%dx%d) -- "
                "falling back to full monitor",
                title, w, h,
            )
            return _capture_full_local()

        import mss
        import mss.tools

        region = {"left": left, "top": top, "width": w, "height": h}
        with mss.mss() as sct:
            img = sct.grab(region)
            png = mss.tools.to_png(img.rgb, img.size)
        b64 = base64.b64encode(png).decode()
        return Screenshot(base64_data=b64, width=w, height=h, mode="window")

    except Exception:
        log.exception("screenshot: unexpected error capturing window %r -- falling back", title)
        return _capture_full_local()


def _find_window(partial_title: str) -> int | None:
    """Return HWND of the first visible window whose title contains
    partial_title (case-insensitive). Returns None if not found.
    """
    try:
        import win32gui

        matches: list[int] = []

        def _cb(hwnd: int, _: object) -> None:
            if win32gui.IsWindowVisible(hwnd):
                if partial_title.lower() in win32gui.GetWindowText(hwnd).lower():
                    matches.append(hwnd)

        win32gui.EnumWindows(_cb, None)
        return matches[0] if matches else None

    except Exception:
        log.exception("screenshot: win32gui.EnumWindows failed")
        return None


def get_screen_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor.

    Falls back to (1920, 1080) if mss is unavailable so callers always
    get a usable value without guarding against None.
    """
    try:
        import mss

        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]
    except Exception:
        log.warning("screenshot: could not read screen size via mss -- defaulting to 1920x1080")
        return 1920, 1080
