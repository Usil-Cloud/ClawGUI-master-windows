"""Windows platform module for ClawGUI-Agent.

Mirrors the interface of phone_agent/xctest/ so DeviceFactory can
route to it without modification to the agent loop.
"""
from phone_agent.windows.connection import (
    ConnectionMode,
    DeviceInfo,
    WindowsConnection,
    is_local,
    list_devices,
    verify_connection,
)
from phone_agent.windows.device import (
    back,
    double_tap,
    get_current_app,
    home,
    launch_app,
    long_press,
    press_enter,
    press_key,
    recent_apps,
    right_click,
    scroll,
    swipe,
    tap,
)
from phone_agent.windows.input import (
    clear_text,
    hotkey,
    type_text,
)
from phone_agent.windows.screenshot import (
    Screenshot,
    get_screenshot,
    get_screen_size,
)
from phone_agent.windows.window_manager import (
    WindowInfo,
    close_window,
    focus_window,
    list_windows,
    maximize_window,
    minimize_window,
)


# ── ADB-compatibility stubs ────────────────────────────────────────────────────
# DeviceFactory calls these methods on whichever module is active.
# Windows has no ADB keyboard; these stubs let the shared action handlers
# (e.g. handler_guiowl._handle_type) call them without branching on device type.

def detect_and_set_adb_keyboard(device_id: str | None = None) -> str:
    """No-op on Windows — system IME is used directly."""
    return "windows-native"


def restore_keyboard(ime: str, device_id: str | None = None) -> None:
    """No-op on Windows — nothing to restore."""
    pass


__all__ = [
    # screenshot
    "get_screenshot",
    "get_screen_size",
    "Screenshot",
    # device
    "tap",
    "double_tap",
    "right_click",
    "long_press",
    "swipe",
    "scroll",
    "back",
    "home",
    "launch_app",
    "get_current_app",
    "press_key",
    "press_enter",
    "recent_apps",
    # input
    "type_text",
    "clear_text",
    "hotkey",
    # window manager
    "focus_window",
    "list_windows",
    "minimize_window",
    "maximize_window",
    "close_window",
    "WindowInfo",
    # connection
    "ConnectionMode",
    "DeviceInfo",
    "WindowsConnection",
    "is_local",
    "list_devices",
    "verify_connection",
    # ADB-compat stubs
    "detect_and_set_adb_keyboard",
    "restore_keyboard",
]
