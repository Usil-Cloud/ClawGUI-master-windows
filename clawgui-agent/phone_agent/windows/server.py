"""
Windows Agent Server — FastAPI REST + FastMCP server on port 7860.

REST API:  http://host:7860/api/*
MCP tools: http://host:7860/mcp  (Model Context Protocol)

Start with:
    python windows_agent_server.py
or:
    uvicorn phone_agent.windows.server:app --host 0.0.0.0 --port 7860

Changes in v1.1.0
-----------------
* Verification envelope: every action endpoint now accepts ``verify: bool = True``.
  When true the server sleeps 0.3 s, captures a screenshot, and returns it
  together with ``active_window``, ``screen`` dims, and ``elapsed_ms``.
* Server-side coord scaling: XYRequest / ScrollRequest / DragRequest now accept
  ``ref_width`` / ``ref_height``.  If supplied the server scales the VLM coords to
  the machine's native resolution automatically — the controller stays stateless.
"""
from __future__ import annotations
import base64
import platform
import socket
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

app = FastAPI(title="Windows Agent Server", version="1.1.0")

# ── Tailscale IP allowlist ─────────────────────────────────────────────────────
# Accept only loopback (local dev) and Tailscale CGNAT range (100.64.0.0/10).
_ALLOWED_PREFIXES = ("127.", "::1", "100.")

@app.middleware("http")
async def tailscale_only(request: Request, call_next):
    client_ip = request.client.host if request.client else ""
    if not any(client_ip.startswith(p) for p in _ALLOWED_PREFIXES):
        return JSONResponse({"error": "forbidden — Tailscale required"}, status_code=403)
    return await call_next(request)

# ── FastMCP server ─────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("windows-agent-server")
    HAS_MCP = True
except ImportError:
    mcp = None
    HAS_MCP = False


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _resolve_coords(
    x: float,
    y: float,
    ref_w: int | None,
    ref_h: int | None,
) -> tuple[int, int]:
    """Scale VLM inference coords to the machine's native resolution.

    If *ref_w* / *ref_h* are provided the function fetches the live screen
    size and linearly scales (x, y).  Otherwise it just casts to int.
    This keeps the controller completely stateless — it never needs to know
    the target resolution.
    """
    if ref_w and ref_h:
        from phone_agent.windows.screenshot import get_screen_size
        native_w, native_h = get_screen_size()
        return int(x * native_w / ref_w), int(y * native_h / ref_h)
    return int(x), int(y)


def _action_response(ok: bool, verify: bool, t0: float) -> dict:
    """Build the standard action-response envelope.

    If *verify* is True the server waits 300 ms for the UI to settle, grabs
    a full-screen screenshot, and includes it (base64 PNG) along with the
    current active window title and screen dimensions.
    ``elapsed_ms`` covers the entire endpoint lifetime including the sleep.
    """
    if verify:
        time.sleep(0.3)
        from phone_agent.windows.screenshot import get_screenshot
        from phone_agent.windows.device import _local_get_current_app
        shot = get_screenshot()
        return {
            "ok": ok,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "screenshot_b64": shot.base64_data,
            "active_window": _local_get_current_app(),
            "screen": {"w": shot.width, "h": shot.height},
        }
    return {
        "ok": ok,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


# ── Pydantic request models ───────────────────────────────────────────────────

class XYRequest(BaseModel):
    x: float
    y: float
    delay: float = 0.5
    ref_width:  int | None = None   # VLM inference width  (for coord scaling)
    ref_height: int | None = None   # VLM inference height (for coord scaling)
    verify: bool = True


class TypeRequest(BaseModel):
    text: str
    verify: bool = True


class HotkeyRequest(BaseModel):
    keys: list[str]
    verify: bool = True


class ScrollRequest(BaseModel):
    x: float
    y: float
    clicks: int = 3
    direction: str = "down"
    ref_width:  int | None = None
    ref_height: int | None = None
    verify: bool = True


class DragRequest(BaseModel):
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    duration_ms: int = 500
    ref_width:  int | None = None
    ref_height: int | None = None
    verify: bool = True


class LaunchRequest(BaseModel):
    app_name: str
    verify: bool = True


class WindowRequest(BaseModel):
    title: str
    verify: bool = True


class ScreenshotRequest(BaseModel):
    window_title: str = ""


class PressKeyRequest(BaseModel):
    key: str
    verify: bool = True


class VerifyRequest(BaseModel):
    """Used for actions with no other parameters (e.g. clear_text)."""
    verify: bool = False            # default OFF — screenshot rarely useful here


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
    t0 = time.time()
    from phone_agent.windows.device import tap
    px, py = _resolve_coords(req.x, req.y, req.ref_width, req.ref_height)
    tap(px, py, delay=req.delay)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/right_click")
def right_click(req: XYRequest):
    t0 = time.time()
    from phone_agent.windows.device import right_click as _rc
    px, py = _resolve_coords(req.x, req.y, req.ref_width, req.ref_height)
    _rc(px, py, delay=req.delay)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/double_click")
def double_click(req: XYRequest):
    t0 = time.time()
    from phone_agent.windows.device import double_tap
    px, py = _resolve_coords(req.x, req.y, req.ref_width, req.ref_height)
    double_tap(px, py, delay=req.delay)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/long_press")
def long_press(req: XYRequest):
    t0 = time.time()
    from phone_agent.windows.device import long_press as _lp
    px, py = _resolve_coords(req.x, req.y, req.ref_width, req.ref_height)
    _lp(px, py, duration_ms=int(req.delay * 1000 or 1000))
    return _action_response(True, req.verify, t0)


@app.post("/api/action/type")
def type_text(req: TypeRequest):
    t0 = time.time()
    from phone_agent.windows.input import type_text as _tt
    _tt(req.text)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/clear_text")
def clear_text(req: VerifyRequest = VerifyRequest()):
    t0 = time.time()
    from phone_agent.windows.input import clear_text as _ct
    _ct()
    return _action_response(True, req.verify, t0)


@app.post("/api/action/hotkey")
def hotkey(req: HotkeyRequest):
    t0 = time.time()
    from phone_agent.windows.input import hotkey as _hk
    _hk(*req.keys)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/press_key")
def press_key(req: PressKeyRequest):
    t0 = time.time()
    from phone_agent.windows.input import press_key as _pk
    _pk(req.key)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/scroll")
def scroll(req: ScrollRequest):
    t0 = time.time()
    from phone_agent.windows.device import scroll as _sc
    px, py = _resolve_coords(req.x, req.y, req.ref_width, req.ref_height)
    _sc(px, py, clicks=req.clicks, direction=req.direction)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/drag")
def drag(req: DragRequest):
    t0 = time.time()
    from phone_agent.windows.device import swipe
    sx, sy = _resolve_coords(req.start_x, req.start_y, req.ref_width, req.ref_height)
    ex, ey = _resolve_coords(req.end_x, req.end_y, req.ref_width, req.ref_height)
    swipe(sx, sy, ex, ey, duration_ms=req.duration_ms)
    return _action_response(True, req.verify, t0)


@app.post("/api/action/launch")
def launch(req: LaunchRequest):
    t0 = time.time()
    from phone_agent.windows.device import launch_app
    ok = launch_app(req.app_name)
    return _action_response(ok, req.verify, t0)


@app.post("/api/action/focus_window")
def focus_window(req: WindowRequest):
    t0 = time.time()
    from phone_agent.windows.window_manager import focus_window as _fw
    ok = _fw(req.title)
    return _action_response(ok, req.verify, t0)


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
    async def click_tool(x: int, y: int, ref_width: int = 0, ref_height: int = 0) -> str:
        """Left-click at screen coordinates with optional VLM coord scaling.

        Args:
            x: X coordinate in pixels (or VLM inference pixels if ref dims given)
            y: Y coordinate in pixels (or VLM inference pixels if ref dims given)
            ref_width:  Width of the image sent to the VLM (0 = no scaling)
            ref_height: Height of the image sent to the VLM (0 = no scaling)
        """
        from phone_agent.windows.device import tap
        px, py = _resolve_coords(x, y, ref_width or None, ref_height or None)
        tap(px, py)
        return f"Clicked ({px}, {py})"

    @mcp.tool()
    async def right_click_tool(x: int, y: int, ref_width: int = 0, ref_height: int = 0) -> str:
        """Right-click at screen coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            ref_width:  VLM inference width  (0 = no scaling)
            ref_height: VLM inference height (0 = no scaling)
        """
        from phone_agent.windows.device import right_click as _rc
        px, py = _resolve_coords(x, y, ref_width or None, ref_height or None)
        _rc(px, py)
        return f"Right-clicked ({px}, {py})"

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
