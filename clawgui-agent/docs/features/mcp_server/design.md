---
mirrors: phone_agent/windows/mcp_server.py
last_updated: 2026-04-30
status: active
---

# MCP Server — Design

## Module layout

```
phone_agent/windows/
  mcp_server.py            # FastMCP entry, 5 @mcp.tool() defs, stdio main
  mcp_handlers/
    __init__.py
    navigate.py            # navigate_windows
    build.py               # build_with_claw (verify loop)
    run_command.py         # run_command (CLI mode)
    inspect.py             # inspect_screen
    session.py             # manage_session
```

`mcp_server.py` contains *only* the 5 tool decorators and the stdio bootstrap.
All real logic lives in `mcp_handlers/`. The 5 decorators are thin pass-through
wrappers — this keeps the rule "5 top-level tools" enforceable by reading one
file.

## Composition (which capability each handler uses)

| Handler | Calls into |
|---|---|
| `navigate.py` | `windows.app_resolver`, `windows.window_manager`, `windows.device`, `windows.input`, `windows.screenshot` |
| `build.py` | `navigate.py` + `perception.gui_owl_adapter` + verify-LLM client (server-side) + `memory.step_memory` |
| `run_command.py` | `subprocess` (stdlib) + optional file capture helpers |
| `inspect.py` | `windows.screenshot` + `perception.gui_owl_adapter` |
| `session.py` | `windows.app_registry` + `memory.step_memory` + `windows.safety` |

## Tool argument shapes (skeleton — finalize during impl)

```python
navigate_windows(goal: str, app: str | None = None, max_steps: int = 8) -> NavigateResult
build_with_claw(goal: str, success_criteria: str, max_iterations: int = 5) -> BuildResult
run_command(cmd: str, cwd: str | None = None, timeout_s: int = 30, capture_files: list[str] | None = None) -> CommandResult
inspect_screen(window_title: str = "", parse: bool = True) -> InspectResult
manage_session(op: str, params: dict | None = None) -> SessionResult
```

`op` for `manage_session` ∈ `{"list_apps", "close_app", "save_memory", "load_memory", "reset", "kill_switch"}`.

Result dataclasses live with their handler module. They are **not** added to
`INTEGRATION_CONTRACT.md` yet — they are MCP-boundary types, not cross-feature
types. If they get consumed elsewhere, promote them.

## Verify loop in `build_with_claw`

Per spec Q2-A, the server runs the LLM verify step. Pseudocode:

```python
def build_with_claw(goal, success_criteria, max_iterations):
    transcript = []
    for i in range(max_iterations):
        plan = llm.plan_next_step(goal, transcript)
        navigate_result = navigate.execute(plan)
        screen_state = inspect.parse(window_title=plan.target_window)
        verdict = llm.judge(goal, success_criteria, screen_state, transcript)
        transcript.append({"plan": plan, "result": navigate_result, "verdict": verdict})
        if verdict.done:
            return BuildResult(success=True, transcript=transcript, final=screen_state)
    return BuildResult(success=False, transcript=transcript, final=screen_state)
```

LLM endpoint: configurable via `phone_agent/config/endpoints.py` (same pattern
1-F uses for the GUI-Owl `/analyze` endpoint).

## Transport

stdio only. Entry point at the bottom of `mcp_server.py`:

```python
if __name__ == "__main__":
    mcp.run()  # FastMCP defaults to stdio
```

Remoting: the Claude Desktop config on the controller machine launches the
server via `ssh user@target-tailscale-ip python -m phone_agent.windows.mcp_server`.
SSH provides auth + transport encryption; Tailscale provides the network
boundary. No auth in the MCP server itself.

## Claude Desktop registration

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows controller):

```json
{
  "mcpServers": {
    "clawgui-windows": {
      "command": "ssh",
      "args": [
        "user@100.x.x.x",
        "python", "-m", "phone_agent.windows.mcp_server"
      ]
    }
  }
}
```

Local-dev variant (no SSH, server runs on the same machine):

```json
{
  "mcpServers": {
    "clawgui-windows-local": {
      "command": "python",
      "args": ["-m", "phone_agent.windows.mcp_server"],
      "cwd": "C:\\Users\\luiso\\Documents\\Projects\\Project Ready Player\\ClawGUI-master\\clawgui-agent"
    }
  }
}
```

## Relationship to the existing FastAPI server

`phone_agent/windows/server.py` keeps its REST endpoints — those are the WAS
HTTP API used by the existing controller-WAS path (1-E `connection.py`). The
MCP block currently embedded in `server.py` is **deprecated**: it exposes 9
capability-shaped tools that violate the goal-shaped rule. It will be removed
once `mcp_server.py` reaches parity.

## Phasing (per spec Q3-A)

1. Walking skeleton: all 5 tools registered, return fake/stub data, stdio boots, Claude Desktop sees the server.
2. Implement `inspect_screen` end-to-end (cheapest — read-only).
3. Implement `navigate_windows` (composes existing 1-A through 1-D).
4. Implement `run_command` (subprocess wrapper).
5. Implement `manage_session` (composes app registry + step memory).
6. Implement `build_with_claw` last (depends on the others + 1-F + verify-LLM).
7. Remove old MCP block from `server.py`. Update `requirements_windows.txt` comment.
