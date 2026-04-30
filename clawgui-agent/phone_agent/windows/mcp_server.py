# Notes: docs/phone_agent/windows/mcp_server.md
"""ClawGUI MCP server — five top-level tools over stdio.

The public surface for ClawGUI-Windows. Every code path the user can invoke
from an MCP client (Claude Desktop, Cursor, Claude Code, ChatGPT desktop)
flows through one of the five `@mcp.tool()` decorators in this file.

Run:
    python -m phone_agent.windows.mcp_server

Remote (controller-machine config calls this via SSH-tunneled stdio):
    ssh user@<tailscale-ip> python -m phone_agent.windows.mcp_server

The five tools are GOAL-SHAPED, not capability-shaped. Adding a sixth tool
here is a design-rule violation — extend a handler module instead.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from phone_agent.windows.mcp_handlers import (
    build,
    inspect,
    navigate,
    session,
)
from phone_agent.windows.mcp_handlers import run_command as run_command_handler

mcp = FastMCP("clawgui-windows")


@mcp.tool()
async def navigate_windows(
    goal: str,
    app: str | None = None,
    max_steps: int = 8,
) -> dict:
    """Reach a UI state on the target Windows machine. Best-effort, no verify.

    Use when the caller wants the agent to open/focus an app and click/type/scroll
    until a position is reached, without proving the goal is complete. Returns
    the final screenshot, active window, and a step trace.

    Args:
        goal: Plain-English description of the desired UI state.
        app: Optional app to ensure is focused first (e.g. "Notepad", "Chrome").
        max_steps: Hard cap on actions dispatched. Default 8.
    """
    return navigate.handle(goal=goal, app=app, max_steps=max_steps)


@mcp.tool()
async def build_with_claw(
    goal: str,
    success_criteria: str,
    max_iterations: int = 5,
) -> dict:
    """Execute a goal end-to-end with a verification loop. Returns pass/fail.

    Use when completion must be verified — the agent plans, acts, re-perceives
    the screen, asks an LLM judge "is the goal complete?", and retries until
    the verdict is True or `max_iterations` is exhausted. Returns a transcript
    plus a final pass/fail.

    Args:
        goal: What to accomplish (plain English).
        success_criteria: How the judge decides "done" (plain English).
        max_iterations: Hard cap on plan→act→verify cycles. Default 5.
    """
    return build.handle(
        goal=goal,
        success_criteria=success_criteria,
        max_iterations=max_iterations,
    )


@mcp.tool()
async def run_command(
    cmd: str,
    cwd: str | None = None,
    timeout_s: int = 30,
    capture_files: list[str] | None = None,
) -> dict:
    """Execute a shell command on the target Windows machine.

    The CLI execution mode of the product (counterpart to the GUI tools).
    Use for file ops, installs, scripts, queries. Returns stdout, stderr,
    exit code, and any requested file captures (base64-encoded).

    Args:
        cmd: Shell command to run.
        cwd: Working directory. None = inherit from server process.
        timeout_s: Hard timeout. Default 30s.
        capture_files: Optional list of paths to read after exec and return inline.
    """
    return run_command_handler.handle(
        cmd=cmd,
        cwd=cwd,
        timeout_s=timeout_s,
        capture_files=capture_files,
    )


@mcp.tool()
async def inspect_screen(window_title: str = "", parse: bool = True) -> dict:
    """Read-only screen probe. No input is dispatched.

    Returns a screenshot plus a structured GUI-Owl screen parse (when
    `parse=True`) so the caller can decide whether to act. The cheap "what's
    on screen?" query before invoking `navigate_windows` or `build_with_claw`.

    Args:
        window_title: Partial title to focus before capture. Empty = full screen.
        parse: If True, run perception adapter and include `screen_state`.
    """
    return inspect.handle(window_title=window_title, parse=parse)


@mcp.tool()
async def manage_session(op: str, params: dict | None = None) -> dict:
    """Co-working session control. One tool, six operations.

    Use to manage state across multiple tool calls in a session: list/close
    agent-spawned apps, save/load step memory, reset the session, or trigger
    the safety kill switch.

    Args:
        op: One of "list_apps", "close_app", "save_memory", "load_memory",
            "reset", "kill_switch".
        params: Op-specific parameters. e.g. close_app needs {"name": "Notepad"}.
    """
    return session.handle(op=op, params=params)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
