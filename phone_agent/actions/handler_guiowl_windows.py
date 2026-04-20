"""
GUI-Owl action handler extended for Windows desktop.

Inherits GUIOwlActionHandler (mobile actions via DeviceFactory) and adds
Windows-specific actions: right_click, hotkey, scroll, drag, focus_window.
These bypass DeviceFactory and call the windows module directly since
DeviceFactory's interface is mobile-only.
"""
from __future__ import annotations
import time

from phone_agent.actions.handler import ActionResult
from phone_agent.actions.handler_guiowl import GUIOwlActionHandler, GUIOwlAction
from phone_agent.device_factory import get_device_factory


class GUIOwlWindowsActionHandler(GUIOwlActionHandler):
    """
    Extends GUIOwlActionHandler with Windows-specific actions.

    Added actions (not in mobile GUIOwlActionHandler):
      - right_click  → pyautogui.rightClick / WAS
      - hotkey       → pyautogui.hotkey / WAS
      - scroll       → pyautogui.scroll / WAS
      - drag         → pyautogui.dragTo / WAS (maps from swipe)
      - focus_window → win32gui.SetForegroundWindow / WAS
      - double_click → pyautogui.doubleClick / WAS

    Overridden actions:
      - system_button → Win-native equivalents (Win key for Home, Alt+F4 for Back)
      - key           → pyautogui.press / hotkey split by '+'
    """

    def _get_handler(self, action_type: str):
        # Windows-specific overrides and additions
        windows_handlers = {
            "right_click": self._handle_right_click,
            "double_click": self._handle_double_click,
            "hotkey": self._handle_hotkey,
            "scroll": self._handle_scroll,
            "drag": self._handle_drag,
            "focus_window": self._handle_focus_window,
            # Override mobile system_button with Win-native equivalents
            "system_button": self._handle_system_button_windows,
            # Override key to support Win hotkey syntax (ctrl+c etc.)
            "key": self._handle_key_windows,
        }
        handler = windows_handlers.get(action_type)
        if handler:
            return handler
        # Fall through to parent for shared actions (click, type, open, etc.)
        return super()._get_handler(action_type)

    # ── Windows-specific handlers ─────────────────────────────────────────────

    def _handle_type(self, params: dict, width: int, height: int) -> ActionResult:
        """
        Override parent _handle_type to skip ADB keyboard logic.

        On Windows there is no ADB IME.  We clear the active field with
        Ctrl+A → Delete, then type directly using pyautogui / WAS.
        """
        import time
        text = params.get("text", "")
        text = text.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')

        from phone_agent.windows.input import clear_text, type_text
        clear_text(device_id=self.device_id)
        time.sleep(0.1)
        type_text(text, device_id=self.device_id)
        return ActionResult(True, False, f"Typed: {text[:50]}")

    def _handle_right_click(self, params: dict, width: int, height: int) -> ActionResult:
        abs_x, abs_y = self._extract_coordinate(params, "coordinate", width, height)
        from phone_agent.windows.device import right_click
        right_click(abs_x, abs_y, device_id=self.device_id)
        return ActionResult(True, False, f"Right-clicked ({abs_x}, {abs_y})")

    def _handle_double_click(self, params: dict, width: int, height: int) -> ActionResult:
        abs_x, abs_y = self._extract_coordinate(params, "coordinate", width, height)
        from phone_agent.windows.device import double_tap
        double_tap(abs_x, abs_y, device_id=self.device_id)
        return ActionResult(True, False, f"Double-clicked ({abs_x}, {abs_y})")

    def _handle_hotkey(self, params: dict, width: int, height: int) -> ActionResult:
        keys_raw = params.get("text", params.get("keys", ""))
        if isinstance(keys_raw, list):
            keys = keys_raw
        else:
            keys = [k.strip() for k in keys_raw.replace("+", ",").split(",")]
        from phone_agent.windows.input import hotkey
        hotkey(*keys, device_id=self.device_id)
        return ActionResult(True, False, f"Hotkey: {'+'.join(keys)}")

    def _handle_scroll(self, params: dict, width: int, height: int) -> ActionResult:
        abs_x, abs_y = self._extract_coordinate(params, "coordinate", width, height)
        # GUI-Owl uses coordinate2 for scroll direction or text field
        direction = params.get("direction", "down")
        clicks = int(params.get("amount", params.get("time", 3)))
        from phone_agent.windows.device import scroll
        scroll(abs_x, abs_y, clicks=clicks, direction=direction, device_id=self.device_id)
        return ActionResult(True, False, f"Scrolled {direction} {clicks}x at ({abs_x}, {abs_y})")

    def _handle_drag(self, params: dict, width: int, height: int) -> ActionResult:
        start_x, start_y = self._extract_coordinate(params, "coordinate", width, height)
        end_x, end_y = self._extract_coordinate(params, "coordinate2", width, height)
        from phone_agent.windows.device import swipe
        swipe(start_x, start_y, end_x, end_y, duration_ms=500, device_id=self.device_id)
        return ActionResult(True, False, f"Dragged ({start_x},{start_y}) → ({end_x},{end_y})")

    def _handle_focus_window(self, params: dict, width: int, height: int) -> ActionResult:
        title = params.get("text", params.get("title", ""))
        if not title:
            return ActionResult(False, False, "No window title specified")
        from phone_agent.windows.window_manager import focus_window
        ok = focus_window(title, device_id=self.device_id)
        if ok:
            return ActionResult(True, False, f"Focused window: {title}")
        return ActionResult(False, False, f"Window not found: {title}")

    def _handle_system_button_windows(self, params: dict, width: int, height: int) -> ActionResult:
        button = params.get("button", "").lower()
        from phone_agent.windows.input import hotkey
        if button == "back":
            hotkey("alt", "F4", device_id=self.device_id)
            return ActionResult(True, False, "Back (Alt+F4)")
        elif button == "home":
            hotkey("win", "d", device_id=self.device_id)
            return ActionResult(True, False, "Home (Win+D)")
        elif button == "menu":
            hotkey("win", "tab", device_id=self.device_id)
            return ActionResult(True, False, "Task View (Win+Tab)")
        elif button == "enter":
            from phone_agent.windows.input import press_key
            press_key("enter", device_id=self.device_id)
            return ActionResult(True, False, "Enter")
        return ActionResult(False, False, f"Unknown button: {button}")

    def _handle_key_windows(self, params: dict, width: int, height: int) -> ActionResult:
        """
        Handles key events. Supports:
        - Single key: {"text": "enter"}
        - Hotkey: {"text": "ctrl+c"} or {"text": "ctrl,c"}
        """
        keycode = params.get("text", params.get("keycode", ""))
        if not keycode:
            return ActionResult(False, False, "No keycode specified")

        from phone_agent.windows.input import hotkey, press_key

        # Detect hotkey combination
        if "+" in keycode or "," in keycode:
            keys = [k.strip() for k in keycode.replace("+", ",").split(",")]
            hotkey(*keys, device_id=self.device_id)
            return ActionResult(True, False, f"Hotkey: {keycode}")

        # Single key press
        press_key(keycode, device_id=self.device_id)
        return ActionResult(True, False, f"Key: {keycode}")
