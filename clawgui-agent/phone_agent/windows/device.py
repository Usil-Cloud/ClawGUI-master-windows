"""Windows device control — matches ClawGUI DeviceFactory interface exactly."""
from __future__ import annotations
import logging
import subprocess
import time

from phone_agent.windows.connection import is_local, post
from phone_agent.windows.app_resolver import AppResolver

log = logging.getLogger(__name__)


def get_current_app(device_id: str | None = None) -> str:
    if is_local(device_id):
        return _local_get_current_app()
    return post(device_id, "/api/info", {}).get("active_window", "Unknown")


def tap(
    x: int, y: int,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.click(x, y)
    else:
        post(device_id, "/api/action/click", {"x": x, "y": y})
    if delay:
        time.sleep(delay)


def double_tap(
    x: int, y: int,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.doubleClick(x, y)
    else:
        post(device_id, "/api/action/double_click", {"x": x, "y": y})
    if delay:
        time.sleep(delay)


def right_click(
    x: int, y: int,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.rightClick(x, y)
    else:
        post(device_id, "/api/action/right_click", {"x": x, "y": y})
    if delay:
        time.sleep(delay)


def long_press(
    x: int, y: int,
    duration_ms: int = 3000,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.mouseDown(x, y)
        time.sleep(duration_ms / 1000)
        pyautogui.mouseUp(x, y)
    else:
        post(device_id, "/api/action/long_press", {"x": x, "y": y, "duration_ms": duration_ms})
    if delay:
        time.sleep(delay)


def swipe(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    duration_ms: int | None = None,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    duration = (duration_ms or 500) / 1000
    if is_local(device_id):
        import pyautogui
        pyautogui.moveTo(start_x, start_y)
        pyautogui.dragTo(end_x, end_y, duration=duration, button="left")
    else:
        post(device_id, "/api/action/drag", {
            "start_x": start_x, "start_y": start_y,
            "end_x": end_x, "end_y": end_y,
            "duration_ms": duration_ms or 500,
        })
    if delay:
        time.sleep(delay)


def scroll(
    x: int, y: int,
    clicks: int = 3,
    direction: str = "down",
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    amount = -clicks if direction == "down" else clicks
    if is_local(device_id):
        import pyautogui
        pyautogui.scroll(amount, x=x, y=y)
    else:
        post(device_id, "/api/action/scroll", {"x": x, "y": y, "clicks": clicks, "direction": direction})
    if delay:
        time.sleep(delay)


def back(device_id: str | None = None, delay: float | None = None) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.hotkey("alt", "F4")
    else:
        post(device_id, "/api/action/hotkey", {"keys": ["alt", "F4"]})
    if delay:
        time.sleep(delay)


def home(device_id: str | None = None, delay: float | None = None) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.hotkey("win", "d")
    else:
        post(device_id, "/api/action/hotkey", {"keys": ["win", "d"]})
    if delay:
        time.sleep(delay)


def launch_app(
    app_name: str,
    device_id: str | None = None,
    delay: float | None = None,
) -> bool:
    if is_local(device_id):
        return _local_launch_app(app_name)
    data = post(device_id, "/api/action/launch", {"app_name": app_name})
    if delay:
        time.sleep(delay)
    return data.get("ok", False)


def press_key(
    keycode: str,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.press(keycode)
    else:
        post(device_id, "/api/action/press_key", {"key": keycode})
    if delay:
        time.sleep(delay)


def press_enter(device_id: str | None = None, delay: float | None = None) -> None:
    press_key("enter", device_id=device_id, delay=delay)


def recent_apps(device_id: str | None = None, delay: float | None = None) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.hotkey("win", "tab")
    else:
        post(device_id, "/api/action/hotkey", {"keys": ["win", "tab"]})
    if delay:
        time.sleep(delay)


# ── local helpers ─────────────────────────────────────────────────────────────

def _local_get_current_app() -> str:
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or "Unknown"
    except Exception:
        return "Unknown"


def _find_running_window(app_name: str) -> int | None:
    """Return hwnd of an existing visible window whose process matches app_name.

    Enumerates all visible top-level windows, resolves each PID to its exe
    filename, and compares against the candidate exe names for app_name.
    Returns the first match, or None if the app is not running.
    """
    try:
        import win32api
        import win32con
        import win32gui
        import win32process
        from pathlib import Path
        from phone_agent.windows.app_resolver import _exe_candidates

        candidates = {c.lower() for c in _exe_candidates(app_name)}
        # also cover simple slug forms not in the alias table
        candidates.add(app_name.lower() + ".exe")
        candidates.add(app_name.lower().replace(" ", "") + ".exe")

        result: list[int] = []

        def _cb(hwnd: int, _) -> bool:
            if result:
                return True  # already found one
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if not win32gui.GetWindowText(hwnd):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                h_proc = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False, pid,
                )
                try:
                    exe = win32process.GetModuleFileNameEx(h_proc, 0)
                    if Path(exe).name.lower() in candidates:
                        result.append(hwnd)
                finally:
                    win32api.CloseHandle(h_proc)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(_cb, None)
        return result[0] if result else None
    except Exception:
        log.debug("device: _find_running_window failed for %r", app_name, exc_info=True)
        return None


def _focus_window(hwnd: int) -> None:
    """Restore (if minimized) and bring hwnd to the foreground."""
    try:
        import win32con
        import win32gui
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        log.debug("device: _focus_window failed for hwnd=%d", hwnd, exc_info=True)


def _local_launch_app(app_name: str) -> bool:
    # Reuse an existing instance rather than spawning a duplicate.
    hwnd = _find_running_window(app_name)
    if hwnd:
        log.debug("device: %r already running (hwnd=%d), focusing", app_name, hwnd)
        _focus_window(hwnd)
        return True

    cmd = AppResolver().resolve(app_name)
    if cmd is None:
        log.warning("device: could not resolve app %r -- launch failed", app_name)
        return False

    # Tier 5 (Start Menu) already performed the launch via pyautogui
    if cmd.tier == 5:
        return True

    try:
        proc = subprocess.Popen(cmd.args)
        log.debug("device: launched %r via tier %d (%s)", app_name, cmd.tier, cmd.resolved_path)
        # Register with the kill switch so it's cleaned up on abort.
        try:
            from phone_agent.windows import safety
            safety.register_process(proc)
        except Exception:
            pass
        return True
    except (FileNotFoundError, OSError) as exc:
        log.error("device: Popen failed for %r (%s): %s", app_name, cmd.resolved_path, exc)
        return False
