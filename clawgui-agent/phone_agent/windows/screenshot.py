"""Windows screenshot capture — smart window vs full-monitor logic."""
from __future__ import annotations
import base64
from dataclasses import dataclass
from io import BytesIO

from phone_agent.windows.connection import is_local, post


@dataclass
class Screenshot:
    """Matches the ClawGUI Screenshot dataclass used by all platform modules."""
    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False


def get_screenshot(
    device_id: str | None = None,
    timeout: int = 10,
    focus_apps: list[str] | None = None,
) -> Screenshot:
    """
    Capture screen. Single app in focus_apps → window-only capture.
    Multiple or no focus_apps → full primary monitor.
    """
    if is_local(device_id):
        if focus_apps and len(focus_apps) == 1:
            return _capture_window_by_title(focus_apps[0])
        return _capture_full_local()
    else:
        window_title = focus_apps[0] if (focus_apps and len(focus_apps) == 1) else None
        data = post(device_id, "/api/screenshot", {"window_title": window_title or ""}, timeout=timeout)
        b64 = data["image"]
        # Decode to get dimensions
        from PIL import Image
        img = Image.open(BytesIO(base64.b64decode(b64)))
        return Screenshot(base64_data=b64, width=img.width, height=img.height)


# ── local implementations ─────────────────────────────────────────────────────

def _capture_full_local() -> Screenshot:
    import mss
    import mss.tools
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        png = mss.tools.to_png(img.rgb, img.size)
    b64 = base64.b64encode(png).decode()
    return Screenshot(base64_data=b64, width=img.width, height=img.height)


def _capture_window_by_title(title: str) -> Screenshot:
    """Capture a specific window by partial title match; fall back to full screen."""
    try:
        import win32gui
        import win32ui
        import win32con
        from PIL import Image

        hwnd = _find_window(title)
        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w, h = right - left, bottom - top
            if w > 0 and h > 0:
                hdc = win32gui.GetWindowDC(hwnd)
                dc_obj = win32ui.CreateDCFromHandle(hdc)
                cdc = dc_obj.CreateCompatibleDC()
                bitmap = win32ui.CreateBitmap()
                bitmap.CreateCompatibleBitmap(dc_obj, w, h)
                cdc.SelectObject(bitmap)
                cdc.BitBlt((0, 0), (w, h), dc_obj, (0, 0), win32con.SRCCOPY)
                bmp_info = bitmap.GetInfo()
                bmp_data = bitmap.GetBitmapBits(True)
                img = Image.frombuffer("RGB", (bmp_info["bmWidth"], bmp_info["bmHeight"]), bmp_data, "raw", "BGRX", 0, 1)
                buf = BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                dc_obj.DeleteDC()
                cdc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hdc)
                win32gui.DeleteObject(bitmap.GetHandle())
                return Screenshot(base64_data=b64, width=w, height=h)
    except Exception:
        pass
    return _capture_full_local()


def _find_window(partial_title: str):
    """Return HWND of first window whose title contains partial_title (case-insensitive)."""
    try:
        import win32gui

        result = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if partial_title.lower() in t.lower():
                    result.append(hwnd)

        win32gui.EnumWindows(callback, None)
        return result[0] if result else None
    except Exception:
        return None


def get_screen_size() -> tuple[int, int]:
    """Return (width, height) of primary monitor."""
    try:
        import mss
        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]
    except Exception:
        return 1920, 1080
