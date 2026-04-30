#!/usr/bin/env python3
"""act.py — Windows Agent Server controller script.

A self-contained CLI that Claude Code (or a human) can use to drive a remote
Windows machine running the WAS (Windows Agent Server).

Usage
-----
    python act.py --host 100.x.x.x [--port 7860] <command> [args...]

Commands
--------
    info                         Print machine info / screen resolution
    screenshot [FILE]            Save a screenshot (default: screenshot_<ts>.png)
    click X Y [--ref WxH]        Left-click at (X, Y); scale if --ref given
    rclick X Y [--ref WxH]       Right-click
    dclick X Y [--ref WxH]       Double-click
    type TEXT                    Type text at current cursor
    hotkey KEY[,KEY...]          Press a keyboard shortcut  (e.g. ctrl,s)
    press KEY                    Press a single key         (e.g. enter)
    scroll X Y [--clicks N] [--dir up|down] [--ref WxH]
    drag SX SY EX EY [--ref WxH] [--ms N]
    launch APP                   Launch application by name
    focus TITLE                  Focus window by partial title
    run TASK_FILE                Execute a JSON task file (multi-step)

Output flags
------------
    --out json   Print the full response envelope to stdout
    --out png    Save the verify screenshot, print its path
    --out both   (default) Do both

Coord scaling
-------------
    Pass --ref 1280x720 when your VLM ran inference on a 1280×720 image.
    WAS will scale the coordinates to the target machine's native resolution.

Task file format (for ``run``)
-------------------------------
    [
        {"action": "click", "params": {"x": 340, "y": 180}, "ref_w": 1280, "ref_h": 720},
        {"action": "type",  "params": {"text": "hello"}},
        {"action": "hotkey","params": {"keys": ["ctrl", "s"]}}
    ]

Exit codes
----------
    0  All actions succeeded
    1  One or more actions failed or the server was unreachable
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

# ── HTTP helper (stdlib only — no extra deps) ──────────────────────────────────

def _http(method: str, url: str, body: dict | None = None, timeout: int = 30) -> dict:
    """Minimal HTTP client using urllib (zero extra dependencies)."""
    import urllib.request
    import urllib.error

    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return json.loads(raw)
        except Exception:
            return {"ok": False, "error": f"HTTP {exc.code}: {raw[:200]}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _get(url: str, timeout: int = 15) -> dict:
    return _http("GET", url, timeout=timeout)


def _post(url: str, body: dict, timeout: int = 30) -> dict:
    return _http("POST", url, body, timeout=timeout)


# ── Session state ──────────────────────────────────────────────────────────────

class Session:
    def __init__(self, host: str, port: int):
        self.base = f"http://{host}:{port}"
        self.native_w: int = 0
        self.native_h: int = 0

    def init(self) -> dict:
        """Fetch /api/info and cache screen dims."""
        resp = _get(f"{self.base}/api/info")
        if "screen" in resp:
            self.native_w = resp["screen"].get("width", 0)
            self.native_h = resp["screen"].get("height", 0)
        return resp

    def action(self, endpoint: str, params: dict) -> dict:
        params.setdefault("verify", True)
        return _post(f"{self.base}/api/action/{endpoint}", params)

    def screenshot_raw(self) -> bytes:
        """Return raw PNG bytes from GET /api/screenshot."""
        import urllib.request
        with urllib.request.urlopen(f"{self.base}/api/screenshot", timeout=15) as r:
            return r.read()


# ── Output helpers ─────────────────────────────────────────────────────────────

def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _save_screenshot(b64: str, prefix: str = "verify") -> Path:
    fname = Path(f"{prefix}_{_ts()}.png")
    fname.write_bytes(base64.b64decode(b64))
    return fname


def _emit(resp: dict, out_mode: str, label: str = "action") -> None:
    """Print JSON and/or save screenshot according to --out mode."""
    if out_mode in ("json", "both"):
        # Print envelope without the bulky screenshot field
        printable = {k: v for k, v in resp.items() if k != "screenshot_b64"}
        if "screenshot_b64" in resp:
            printable["screenshot_saved"] = "(see png output)"
        print(json.dumps(printable, indent=2))

    if out_mode in ("png", "both"):
        b64 = resp.get("screenshot_b64")
        if b64:
            path = _save_screenshot(b64, prefix=label)
            print(f"[verify] {path.resolve()}")
        else:
            if out_mode == "png":
                print("[verify] No screenshot in response (verify=False or not supported)")


def _check_ok(resp: dict, label: str) -> bool:
    ok = resp.get("ok", False)
    if not ok:
        err = resp.get("error", resp)
        print(f"[FAIL] {label}: {err}", file=sys.stderr)
    return ok


# ── Coord scaling helper ───────────────────────────────────────────────────────

def _parse_ref(ref_str: str | None) -> tuple[int | None, int | None]:
    """Parse '1280x720' → (1280, 720). Returns (None, None) if ref_str is falsy."""
    if not ref_str:
        return None, None
    try:
        w, h = ref_str.lower().split("x")
        return int(w), int(h)
    except Exception:
        print(f"[warn] Could not parse --ref '{ref_str}' — ignoring scaling", file=sys.stderr)
        return None, None


# ── Command implementations ────────────────────────────────────────────────────

def cmd_info(session: Session, _args: argparse.Namespace) -> bool:
    resp = session.init()
    print(json.dumps(resp, indent=2))
    return True


def cmd_screenshot(session: Session, args: argparse.Namespace) -> bool:
    raw = session.screenshot_raw()
    dest = Path(getattr(args, "file", None) or f"screenshot_{_ts()}.png")
    dest.write_bytes(raw)
    print(f"[screenshot] {dest.resolve()}  ({len(raw):,} bytes)")
    return True


def cmd_click(session: Session, args: argparse.Namespace, endpoint: str = "click") -> bool:
    ref_w, ref_h = _parse_ref(args.ref)
    params: dict[str, Any] = {"x": args.x, "y": args.y, "delay": args.delay}
    if ref_w:
        params["ref_width"] = ref_w
        params["ref_height"] = ref_h
    resp = session.action(endpoint, params)
    _emit(resp, args.out, label=endpoint)
    return _check_ok(resp, endpoint)


def cmd_type(session: Session, args: argparse.Namespace) -> bool:
    resp = session.action("type", {"text": args.text})
    _emit(resp, args.out, label="type")
    return _check_ok(resp, "type")


def cmd_hotkey(session: Session, args: argparse.Namespace) -> bool:
    keys = [k.strip() for k in args.keys.split(",")]
    resp = session.action("hotkey", {"keys": keys})
    _emit(resp, args.out, label="hotkey")
    return _check_ok(resp, "hotkey")


def cmd_press(session: Session, args: argparse.Namespace) -> bool:
    resp = session.action("press_key", {"key": args.key})
    _emit(resp, args.out, label="press_key")
    return _check_ok(resp, "press_key")


def cmd_scroll(session: Session, args: argparse.Namespace) -> bool:
    ref_w, ref_h = _parse_ref(args.ref)
    params: dict[str, Any] = {
        "x": args.x, "y": args.y,
        "clicks": args.clicks,
        "direction": args.dir,
    }
    if ref_w:
        params["ref_width"] = ref_w
        params["ref_height"] = ref_h
    resp = session.action("scroll", params)
    _emit(resp, args.out, label="scroll")
    return _check_ok(resp, "scroll")


def cmd_drag(session: Session, args: argparse.Namespace) -> bool:
    ref_w, ref_h = _parse_ref(args.ref)
    params: dict[str, Any] = {
        "start_x": args.sx, "start_y": args.sy,
        "end_x":   args.ex, "end_y":   args.ey,
        "duration_ms": args.ms,
    }
    if ref_w:
        params["ref_width"] = ref_w
        params["ref_height"] = ref_h
    resp = session.action("drag", params)
    _emit(resp, args.out, label="drag")
    return _check_ok(resp, "drag")


def cmd_launch(session: Session, args: argparse.Namespace) -> bool:
    resp = session.action("launch", {"app_name": args.app})
    _emit(resp, args.out, label="launch")
    return _check_ok(resp, "launch")


def cmd_focus(session: Session, args: argparse.Namespace) -> bool:
    resp = session.action("focus_window", {"title": args.title})
    _emit(resp, args.out, label="focus_window")
    return _check_ok(resp, "focus_window")


def cmd_run(session: Session, args: argparse.Namespace) -> bool:
    """Execute a JSON task file: [{action, params, ref_w?, ref_h?}, ...]"""
    task_path = Path(args.task_file)
    if not task_path.exists():
        print(f"[error] Task file not found: {task_path}", file=sys.stderr)
        return False

    steps: list[dict] = json.loads(task_path.read_text())
    print(f"[run] {len(steps)} step(s) from {task_path.name}")
    all_ok = True

    for i, step in enumerate(steps, 1):
        action   = step.get("action", "")
        params   = dict(step.get("params", {}))
        ref_w    = step.get("ref_w")
        ref_h    = step.get("ref_h")
        delay_before = step.get("delay_before", 0)

        if delay_before:
            time.sleep(delay_before)

        if ref_w and ref_h:
            params["ref_width"]  = ref_w
            params["ref_height"] = ref_h

        print(f"[{i}/{len(steps)}] {action} {params}")
        resp = session.action(action, params)
        _emit(resp, args.out, label=f"step{i:02d}_{action}")

        if not _check_ok(resp, f"step {i} ({action})"):
            print(f"[run] Aborting at step {i} — action failed.", file=sys.stderr)
            all_ok = False
            break

    status = "completed" if all_ok else "FAILED"
    print(f"[run] {status}  ({i}/{len(steps)} steps executed)")
    return all_ok


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="act.py",
        description="Windows Agent Server controller — drive a remote Windows machine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--host",   required=True,  help="WAS host (Tailscale IP or hostname)")
    p.add_argument("--port",   type=int, default=7860, help="WAS port (default: 7860)")
    p.add_argument("--out",    choices=["json", "png", "both"], default="both",
                   help="Output mode (default: both)")

    sub = p.add_subparsers(dest="command", required=True)

    # info
    sub.add_parser("info", help="Print machine info and screen resolution")

    # screenshot
    sp = sub.add_parser("screenshot", help="Capture and save a screenshot")
    sp.add_argument("file", nargs="?", help="Output filename (default: screenshot_<ts>.png)")

    # click / rclick / dclick  (shared helper)
    for cmd, help_txt in [
        ("click",  "Left-click at (X, Y)"),
        ("rclick", "Right-click at (X, Y)"),
        ("dclick", "Double-click at (X, Y)"),
    ]:
        sp = sub.add_parser(cmd, help=help_txt)
        sp.add_argument("x", type=float)
        sp.add_argument("y", type=float)
        sp.add_argument("--ref",   default=None,  help="VLM resolution, e.g. 1280x720")
        sp.add_argument("--delay", type=float, default=0.5, help="Post-action delay (s)")

    # type
    sp = sub.add_parser("type", help="Type text at the current cursor position")
    sp.add_argument("text")

    # hotkey
    sp = sub.add_parser("hotkey", help="Press a keyboard shortcut (comma-separated)")
    sp.add_argument("keys", help="e.g. ctrl,s  or  win,d")

    # press
    sp = sub.add_parser("press", help="Press a single key")
    sp.add_argument("key", help="e.g. enter, tab, escape")

    # scroll
    sp = sub.add_parser("scroll", help="Scroll the mouse wheel")
    sp.add_argument("x", type=float)
    sp.add_argument("y", type=float)
    sp.add_argument("--clicks", type=int, default=3)
    sp.add_argument("--dir", choices=["up", "down"], default="down")
    sp.add_argument("--ref",   default=None, help="VLM resolution, e.g. 1280x720")

    # drag
    sp = sub.add_parser("drag", help="Click-drag from one point to another")
    sp.add_argument("sx", type=float, metavar="START_X")
    sp.add_argument("sy", type=float, metavar="START_Y")
    sp.add_argument("ex", type=float, metavar="END_X")
    sp.add_argument("ey", type=float, metavar="END_Y")
    sp.add_argument("--ref", default=None, help="VLM resolution, e.g. 1280x720")
    sp.add_argument("--ms",  type=int, default=500, help="Drag duration in ms")

    # launch
    sp = sub.add_parser("launch", help="Launch a Windows application by name")
    sp.add_argument("app")

    # focus
    sp = sub.add_parser("focus", help="Focus window by partial title match")
    sp.add_argument("title")

    # run
    sp = sub.add_parser("run", help="Execute a JSON task file (multi-step)")
    sp.add_argument("task_file")

    return p


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    session = Session(args.host, args.port)

    # For non-info commands that send actions, pre-fetch screen dims
    # (best-effort — failure is non-fatal; WAS can scale server-side anyway)
    if args.command not in ("info", "screenshot"):
        try:
            session.init()
        except Exception:
            pass  # server will handle scaling itself

    _COMMAND_MAP = {
        "info":       cmd_info,
        "screenshot": cmd_screenshot,
        "click":      lambda s, a: cmd_click(s, a, "click"),
        "rclick":     lambda s, a: cmd_click(s, a, "right_click"),
        "dclick":     lambda s, a: cmd_click(s, a, "double_click"),
        "type":       cmd_type,
        "hotkey":     cmd_hotkey,
        "press":      cmd_press,
        "scroll":     cmd_scroll,
        "drag":       cmd_drag,
        "launch":     cmd_launch,
        "focus":      cmd_focus,
        "run":        cmd_run,
    }

    handler = _COMMAND_MAP.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    ok = handler(session, args)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
