# Notes: docs/phone_agent/windows/mcp_handlers/navigate.md
"""Handler for the `navigate_windows` MCP tool.

Best-effort GUI navigation: open/focus app, click/type/scroll until a goal
position is reached. No completion verification — see `build.py` for that.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class NavigateResult:
    ok: bool
    final_screenshot_b64: str
    active_window: str
    steps_taken: int
    notes: list[str] = field(default_factory=list)


def handle(goal: str, app: str | None = None, max_steps: int = 8) -> dict:
    # TODO(1-H/navigate): plan steps from goal, dispatch via app_resolver +
    # window_manager + device + input, capture final screenshot.
    result = NavigateResult(
        ok=False,
        final_screenshot_b64="",
        active_window="",
        steps_taken=0,
        notes=[f"stub: goal={goal!r} app={app!r} max_steps={max_steps}"],
    )
    return asdict(result)
