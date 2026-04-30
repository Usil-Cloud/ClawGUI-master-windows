# Notes: docs/phone_agent/windows/mcp_handlers/inspect.md
"""Handler for the `inspect_screen` MCP tool.

Read-only probe: screenshot + (optional) GUI-Owl screen parse. The cheapest
of the five tools — no input is dispatched, no state is mutated.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class InspectResult:
    ok: bool
    screenshot_b64: str
    width: int
    height: int
    active_window: str
    screen_state: dict | None = None
    notes: list[str] = field(default_factory=list)


def handle(window_title: str = "", parse: bool = True) -> dict:
    notes: list[str] = []

    if window_title:
        from phone_agent.windows.window_manager import focus_window
        if not focus_window(window_title):
            notes.append(f"focus_window({window_title!r}) returned False — full capture used")

    try:
        from phone_agent.windows.screenshot import get_screenshot
        shot = get_screenshot(focus_apps=[window_title] if window_title else None)
    except Exception as exc:
        return asdict(InspectResult(
            ok=False,
            screenshot_b64="",
            width=0,
            height=0,
            active_window="",
            notes=[f"screenshot failed: {exc}"],
        ))

    active_window = ""
    try:
        import win32gui
        active_window = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    except Exception as exc:
        notes.append(f"active_window query failed: {exc}")

    screen_state: dict | None = None
    if parse:
        from phone_agent.perception.gui_owl_adapter import GUIOwlAdapter
        state = GUIOwlAdapter().analyze(shot)
        screen_state = {
            "elements": [
                {
                    "label": el.label,
                    "bbox": list(el.bbox),
                    "confidence": el.confidence,
                    "element_type": el.element_type,
                }
                for el in state.elements
            ],
            "planned_action": state.planned_action,
            "reflection": state.reflection,
        }
        if state.raw_response.get("fallback"):
            notes.append(
                f"GUI-Owl fallback at {state.raw_response.get('failed_step')!r}: "
                f"{state.raw_response.get('error')}"
            )

    return asdict(InspectResult(
        ok=True,
        screenshot_b64=shot.base64_data,
        width=shot.width,
        height=shot.height,
        active_window=active_window,
        screen_state=screen_state,
        notes=notes,
    ))
