# Notes: docs/phone_agent/windows/mcp_handlers/build.md
"""Handler for the `build_with_claw` MCP tool.

Runs a verification loop: plan → act → re-perceive → judge → retry. The
server owns the LLM verify step (per spec Q2-A). See
`docs/features/mcp_server/design.md` for the loop pseudocode.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class BuildResult:
    success: bool
    iterations: int
    transcript: list[dict] = field(default_factory=list)
    final_screenshot_b64: str = ""
    final_active_window: str = ""
    notes: list[str] = field(default_factory=list)


def handle(goal: str, success_criteria: str, max_iterations: int = 5) -> dict:
    # TODO(1-H/build): per-iteration plan via LLM, call navigate.handle,
    # call inspect.handle for screen state, call LLM judge, loop until done
    # or max_iterations exhausted. Persist transcript via step_memory.
    result = BuildResult(
        success=False,
        iterations=0,
        notes=[
            f"stub: goal={goal!r} success_criteria={success_criteria!r} "
            f"max_iterations={max_iterations}"
        ],
    )
    return asdict(result)
