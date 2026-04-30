# Notes: docs/phone_agent/windows/mcp_handlers/session.md
"""Handler for the `manage_session` MCP tool.

Co-working session control. One tool, one `op` argument, six operations.
Owns the multi-turn / cross-call state the other four tools shouldn't carry
on their argument lists.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict

VALID_OPS = {
    "list_apps",
    "close_app",
    "save_memory",
    "load_memory",
    "reset",
    "kill_switch",
}


@dataclass
class SessionResult:
    ok: bool
    op: str
    data: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def handle(op: str, params: dict | None = None) -> dict:
    params = params or {}
    if op not in VALID_OPS:
        result = SessionResult(
            ok=False,
            op=op,
            notes=[f"unknown op: {op!r}. valid: {sorted(VALID_OPS)}"],
        )
        return asdict(result)

    # TODO(1-H/session): dispatch by op into app_registry, step_memory, safety.
    result = SessionResult(
        ok=False,
        op=op,
        notes=[f"stub: op={op!r} params={params!r}"],
    )
    return asdict(result)
