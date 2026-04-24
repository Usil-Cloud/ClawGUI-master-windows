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


def _local_launch_app(app_name: str) -> bool:
    cmd = AppResolver().resolve(app_name)
    if cmd is None:
        log.warning("device: could not resolve app %r -- launch failed", app_name)
        return False

    # Tier 5 (Start Menu) already performed the launch via pyautogui
    if cmd.tier == 5:
        return True

    try:
        subprocess.Popen(cmd.args)
        log.debug("device: launched %r via tier %d (%s)", app_name, cmd.tier, cmd.resolved_path)
        return True
    except (FileNotFoundError, OSError) as exc:
        log.error("device: Popen failed for %r (%s): %s", app_name, cmd.resolved_path, exc)
        return False
