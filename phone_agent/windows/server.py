"""
Windows Agent Server — FastAPI REST + FastMCP server on port 7860.

REST API:  http://host:7860/api/*
MCP tools: http://host:7860/mcp  (Model Context Protocol)

Start with:
    python windows_agent_server.py
or:
    uvicorn phone_agent.windows.server:app --host 0.0.0.0 --port 7860
"""
from __future__ import annotations
import base64
import platform
import socket

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="Windows Agent Server", version="1.0.0")

# ── FastMCP server ─────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("windows-agent-server")
    HAS_MCP = True
except ImportError:
    mcp = None
    HAS_MCP = False

# ── Pydantic request models ───────────────────────────────────────────────────

class XYRequest(BaseModel):
    x: int
    y: int
    delay: float = 0.5

class TypeRequest(BaseModel):
    text: str

class HotkeyRequest(BaseModel):
    keys: list[str]

class ScrollRequest(BaseModel):
    x: int
    y: int
    clicks: int = 3
    direction: str = "down"

class DragRequest(BaseModel):
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    duration_ms: int = 500

class LaunchRequest(BaseModel):
    app_name: str

class WindowRequest(BaseModel):
    title: str

class ScreenshotRequest(BaseModel):
    window_title: str = ""

class PressKeyRequest(BaseModel):
    key: str


# ── REST endpoints (/api/*) ───────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    from phone_agent.windows.screenshot import get_screen_size
    from phone_agent.windows.device import _local_get_current_app
    w, h = get_screen_size()
    return {
        "machine": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "screen": {"width": w, "height": h},
        "active_window": _local_get_current_app(),
    }


@app.get("/api/screenshot")
def screenshot_get():
    from phone_agent.windows.screenshot import get_screenshot
    shot = get_screenshot()
    return Response(content=base64.b64decode(shot.base64_data), media_type="image/png")


@app.post("/api/screenshot")
def screenshot(req: ScreenshotRequest):
    from phone_agent.windows.screenshot import get_screenshot
    shot = get_screenshot(focus_apps=[req.window_title] if req.window_title else None)
    return {"image": shot.base64_data, "width": shot.width, "height": shot.height, "format": "png"}


@app.post("/api/action/click")
def click(req: XYRequest):
    from phone_agent.windows.device import tap
    tap(req.x, req.y, delay=req.delay)
    return {"ok": True}


@app.post("/api/action/right_click")
def right_click(req: XYRequest):
    from phone_agent.windows.device import right_click as _rc
    _rc(req.x, req.y, delay=req.delay)
    return {"ok": True}


@app.post("/api/action/double_click")
def double_click(req: XYRequest):
    from phone_agent.windows.device import double_tap
    double_tap(req.x, req.y, delay=req.delay)
    return {"ok": True}


@app.post("/api/action/long_press")
def long_press(req: XYRequest):
    from phone_agent.windows.device import long_press as _lp
    _lp(req.x, req.y, duration_ms=int(req.delay * 1000 or 1000))
    return {"ok": True}


@app.post("/api/action/type")
def type_text(req: TypeRequest):
    from phone_agent.windows.input import type_text as _tt
    _tt(req.text)
    return {"ok": True}


@app.post("/api/action/clear_text")
def clear_text():
    from phone_agent.windows.input import clear_text as _ct
    _ct()
    return {"ok": True}


@app.post("/api/action/hotkey")
def hotkey(req: HotkeyRequest):
    from phone_agent.windows.input import hotkey as _hk
    _hk(*req.keys)
    return {"ok": True}


@app.post("/api/action/press_key")
def press_key(req: PressKeyRequest):
    from phone_agent.windows.input import press_key as _pk
    _pk(req.key)
    return {"ok": True}


@app.post("/api/action/scroll")
def scroll(req: ScrollRequest):
    from phone_agent.windows.device import scroll as _sc
    _sc(req.x, req.y, clicks=req.clicks, direction=req.direction)
    return {"ok": True}


@app.post("/api/action/drag")
def drag(req: DragRequest):
    from phone_agent.windows.device import swipe
    swipe(req.start_x, req.start_y, req.end_x, req.end_y, duration_ms=req.duration_ms)
    return {"ok": True}


@app.post("/api/action/launch")
def launch(req: LaunchRequest):
    from phone_agent.windows.device import launch_app
    ok = launch_app(req.app_name)
    return {"ok": ok}


@app.post("/api/action/focus_window")
def focus_window(req: WindowRequest):
    from phone_agent.windows.window_manager import focus_window as _fw
    ok = _fw(req.title)
    return {"ok": ok}


@app.get("/api/windows/list")
def list_windows():
    from phone_agent.windows.window_manager import list_windows as _lw
    return {"windows": [{"hwnd": w.hwnd, "title": w.title, "visible": w.visible} for w in _lw()]}


# ── MCP tools ─────────────────────────────────────────────────────────────────
# Only registered if mcp package is available.

if HAS_MCP and mcp is not None:

    @mcp.tool()
    async def screenshot_tool(window_title: str = "") -> str:
        """Capture the screen or a specific window and return base64 PNG.

        Args:
            window_title: Optional partial window title. Empty = full screen.
        """
        from phone_agent.windows.screenshot import get_screenshot
        shot = get_screenshot(focus_apps=[window_title] if window_title else None)
        return shot.base64_data

    @mcp.tool()
    async def click_tool(x: int, y: int) -> str:
        """Left-click at screen coordinates.

        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels
        """
        from phone_agent.windows.device import tap
        tap(x, y)
        return f"Clicked ({x}, {y})"

    @mcp.tool()
    async def right_click_tool(x: int, y: int) -> str:
        """Right-click at screen coordinates.

        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels
        """
        from phone_agent.windows.device import right_click as _rc
        _rc(x, y)
        return f"Right-clicked ({x}, {y})"

    @mcp.tool()
    async def type_text_tool(text: str) -> str:
        """Type text at the current cursor position.

        Args:
            text: Text to type
        """
        from phone_agent.windows.input import type_text as _tt
        _tt(text)
        return f"Typed {len(text)} characters"

    @mcp.tool()
    async def hotkey_tool(keys: str) -> str:
        """Press a keyboard shortcut (comma-separated key names).

        Args:
            keys: Comma-separated key names, e.g. 'ctrl,c' or 'win,d'
        """
        from phone_agent.windows.input import hotkey as _hk
        _hk(*keys.split(","))
        return f"Pressed hotkey: {keys}"

    @mcp.tool()
    async def scroll_tool(x: int, y: int, clicks: int = 3, direction: str = "down") -> str:
        """Scroll the mouse wheel at a position.

        Args:
            x: X coordinate
            y: Y coordinate
            clicks: Number of scroll clicks
            direction: 'up' or 'down'
        """
        from phone_agent.windows.device import scroll as _sc
        _sc(x, y, clicks=clicks, direction=direction)
        return f"Scrolled {direction} {clicks}x at ({x}, {y})"

    @mcp.tool()
    async def launch_app_tool(app_name: str) -> str:
        """Launch a Windows application by name.

        Args:
            app_name: Application display name (e.g. 'Notepad', 'Chrome')
        """
        from phone_agent.windows.device import launch_app
        ok = launch_app(app_name)
        return "Launched" if ok else f"Could not launch: {app_name}"

    @mcp.tool()
    async def focus_window_tool(title: str) -> str:
        """Bring a window to the foreground by partial title match.

        Args:
            title: Full or partial window title to match
        """
        from phone_agent.windows.window_manager import focus_window as _fw
        ok = _fw(title)
        return "Focused" if ok else f"Window not found: {title}"

    @mcp.tool()
    async def get_info_tool() -> str:
        """Return machine hostname, OS version, and screen resolution."""
        from phone_agent.windows.screenshot import get_screen_size
        w, h = get_screen_size()
        return f"{socket.gethostname()} | {platform.system()} {platform.release()} | {w}x{h}"

    # Mount MCP ASGI app on /mcp path
    try:
        mcp_app = mcp.get_asgi_app()
        app.mount("/mcp", mcp_app)
    except Exception:
        # FastMCP version may not support get_asgi_app() — skip silently
        pass
