"""Windows keyboard input — type_text, hotkey, clear_text."""
from __future__ import annotations
import time

from phone_agent.windows.connection import is_local, post


def type_text(text: str, device_id: str | None = None) -> None:
    if is_local(device_id):
        _local_type(text)
    else:
        post(device_id, "/api/action/type", {"text": text})


def clear_text(device_id: str | None = None) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("delete")
    else:
        post(device_id, "/api/action/clear_text", {})


def hotkey(*keys: str, device_id: str | None = None) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.hotkey(*keys)
    else:
        post(device_id, "/api/action/hotkey", {"keys": list(keys)})


def press_key(key: str, device_id: str | None = None) -> None:
    if is_local(device_id):
        import pyautogui
        pyautogui.press(key)
    else:
        post(device_id, "/api/action/press_key", {"key": key})


# ── local helpers ─────────────────────────────────────────────────────────────

def _local_type(text: str) -> None:
    """Type text, using clipboard for non-ASCII characters."""
    import pyautogui

    has_non_ascii = any(ord(c) > 127 for c in text)

    if has_non_ascii:
        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return
        except ImportError:
            pass

    # ASCII-safe typewrite with interval
    pyautogui.typewrite(text, interval=0.02)
