"""Windows window management — focus, enumerate, min/max/close."""
from __future__ import annotations
from dataclasses import dataclass

from phone_agent.windows.connection import is_local, post


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    visible: bool


def focus_window(title: str, device_id: str | None = None) -> bool:
    """Bring window with matching title to foreground."""
    if is_local(device_id):
        return _local_focus(title)
    data = post(device_id, "/api/action/focus_window", {"title": title})
    return data.get("ok", False)


def list_windows(device_id: str | None = None) -> list[WindowInfo]:
    if is_local(device_id):
        return _local_list_windows()
    data = post(device_id, "/api/windows/list", {})
    return [WindowInfo(w["hwnd"], w["title"], w["visible"]) for w in data.get("windows", [])]


def minimize_window(title: str, device_id: str | None = None) -> bool:
    if is_local(device_id):
        return _local_set_window_state(title, "minimize")
    data = post(device_id, "/api/windows/minimize", {"title": title})
    return data.get("ok", False)


def maximize_window(title: str, device_id: str | None = None) -> bool:
    if is_local(device_id):
        return _local_set_window_state(title, "maximize")
    data = post(device_id, "/api/windows/maximize", {"title": title})
    return data.get("ok", False)


def close_window(title: str, device_id: str | None = None) -> bool:
    if is_local(device_id):
        return _local_set_window_state(title, "close")
    data = post(device_id, "/api/windows/close", {"title": title})
    return data.get("ok", False)


# ── local helpers ─────────────────────────────────────────────────────────────

def _find_hwnd(partial_title: str) -> int | None:
    try:
        import win32gui
        result: list[int] = []

        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if partial_title.lower() in t.lower():
                    result.append(hwnd)

        win32gui.EnumWindows(cb, None)
        return result[0] if result else None
    except Exception:
        return None


def _local_focus(title: str) -> bool:
    try:
        import win32gui
        import win32con
        hwnd = _find_hwnd(title)
        if hwnd:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
    except Exception:
        pass
    return False


def _local_list_windows() -> list[WindowInfo]:
    try:
        import win32gui
        windows: list[WindowInfo] = []

        def cb(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append(WindowInfo(hwnd=hwnd, title=title, visible=win32gui.IsWindowVisible(hwnd)))

        win32gui.EnumWindows(cb, None)
        return windows
    except Exception:
        return []


def _local_set_window_state(title: str, state: str) -> bool:
    try:
        import win32gui
        import win32con
        hwnd = _find_hwnd(title)
        if not hwnd:
            return False
        cmd = {"minimize": win32con.SW_MINIMIZE, "maximize": win32con.SW_MAXIMIZE, "close": win32con.SC_CLOSE}
        if state == "close":
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        else:
            win32gui.ShowWindow(hwnd, cmd[state])
        return True
    except Exception:
        return False
