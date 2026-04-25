"""Windows window management — focus, enumerate, min/max/close."""
from __future__ import annotations
from dataclasses import dataclass

from phone_agent.windows.connection import is_local, post


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    visible: bool
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)


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
    return [
        WindowInfo(w["hwnd"], w["title"], w["visible"], tuple(w.get("rect", [0, 0, 0, 0])))
        for w in data.get("windows", [])
    ]


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
        import win32con
        import win32gui
        import win32process

        hwnd = _find_hwnd(title)
        if not hwnd:
            return False

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Two-step focus strategy that works even when an Electron/CEF app
        # (VS Code, Discord) holds foreground and fights SetForegroundWindow:
        #
        # 1. AttachThreadInput: transfers the foreground lock from the current
        #    foreground thread to the target thread.
        # 2. TOPMOST flip: briefly promote the window to always-on-top then
        #    demote it.  This wins the z-order contest even if the previous
        #    foreground owner immediately reclaims focus, because the demotion
        #    step resets its position as the top normal window.
        fg_hwnd = win32gui.GetForegroundWindow()
        fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
        tgt_tid = win32process.GetWindowThreadProcessId(hwnd)[0]
        attached = False
        if fg_tid and tgt_tid and fg_tid != tgt_tid:
            attached = bool(win32process.AttachThreadInput(fg_tid, tgt_tid, True))
        try:
            _SWP = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,   0, 0, 0, 0, _SWP)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, _SWP | win32con.SWP_SHOWWINDOW)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                win32process.AttachThreadInput(fg_tid, tgt_tid, False)
        return True
    except Exception:
        return False


def _local_list_windows() -> list[WindowInfo]:
    try:
        import win32gui
        windows: list[WindowInfo] = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            rect = win32gui.GetWindowRect(hwnd)
            windows.append(WindowInfo(hwnd=hwnd, title=title, visible=True, rect=rect))

        win32gui.EnumWindows(cb, None)
        return windows
    except Exception:
        return []


def _kill_window_process(hwnd: int) -> None:
    """Terminate the process that owns hwnd via TerminateProcess.

    Bypasses any blocking dialog (e.g. "save changes?") because it kills the
    window owner at the OS level, not via a window message.  Used as a
    fallback when WM_CLOSE leaves the window alive.
    """
    try:
        import win32api
        import win32con
        import win32process
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return
        h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)
        try:
            win32api.TerminateProcess(h_proc, 1)
        finally:
            win32api.CloseHandle(h_proc)
    except Exception:
        pass


def _local_set_window_state(title: str, state: str) -> bool:
    try:
        import time
        import win32con
        import win32gui
        hwnd = _find_hwnd(title)
        if not hwnd:
            return False
        if state == "close":
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            # Give the app a brief window to close cleanly, then force-kill
            # the owning process if a blocking dialog prevented the close.
            time.sleep(0.5)
            if win32gui.IsWindow(hwnd):
                _kill_window_process(hwnd)
        else:
            cmd = {"minimize": win32con.SW_MINIMIZE, "maximize": win32con.SW_MAXIMIZE}
            win32gui.ShowWindow(hwnd, cmd[state])
        return True
    except Exception:
        return False
