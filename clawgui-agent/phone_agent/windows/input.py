"""Windows keyboard input — type_text, hotkey, press_key, clear_text."""
from __future__ import annotations
import time

from phone_agent.windows.connection import is_local, post

_DEFAULT_INTERVAL = 0.05  # seconds between characters


def type_text(text: str, device_id: str | None = None, interval: float = _DEFAULT_INTERVAL) -> None:
    if is_local(device_id):
        _local_type(text, interval=interval)
    else:
        post(device_id, "/api/action/type", {"text": text, "interval": interval})


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

def _local_type(text: str, interval: float = _DEFAULT_INTERVAL) -> None:
    import pyautogui

    if _has_non_ascii(text):
        _clipboard_paste(text)
        return

    pyautogui.typewrite(text, interval=interval)


def _has_non_ascii(text: str) -> bool:
    return any(ord(c) > 127 for c in text)


def _clipboard_paste(text: str) -> None:
    """Write text to clipboard via win32clipboard then paste with Ctrl+V."""
    import pyautogui

    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            # CF_UNICODETEXT requires a null-terminated wide string
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        pyautogui.hotkey("ctrl", "v")
        return
    except ImportError:
        pass

    # Fallback: pyperclip (keeps prior behaviour when win32clipboard absent)
    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except ImportError:
        # Last resort: typewrite and accept potential character drops
        pyautogui.typewrite(text, interval=0.05)
