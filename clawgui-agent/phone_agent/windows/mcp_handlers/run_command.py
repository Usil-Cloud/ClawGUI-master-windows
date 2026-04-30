# Notes: docs/phone_agent/windows/mcp_handlers/run_command.md
"""Handler for the `run_command` MCP tool.

CLI execution mode. `subprocess.run` with optional cwd, timeout, and post-exec
file capture (returned base64-encoded so the client sees them inline).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class CommandResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    captured_files: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def handle(
    cmd: str,
    cwd: str | None = None,
    timeout_s: int = 30,
    capture_files: list[str] | None = None,
) -> dict:
    # TODO(1-H/run_command): subprocess.run with shell=True on Windows,
    # capture stdout/stderr as utf-8/replace, read capture_files post-exec
    # and base64-encode them into captured_files.
    result = CommandResult(
        ok=False,
        exit_code=-1,
        stdout="",
        stderr="",
        elapsed_ms=0,
        notes=[
            f"stub: cmd={cmd!r} cwd={cwd!r} timeout_s={timeout_s} "
            f"capture_files={capture_files!r}"
        ],
    )
    return asdict(result)
