"""Windows connection mode detection and remote HTTP client.

Phase 1-E adds a transparent local/remote split:
    * detect_mode(device_id)   -> ConnectionProfile
    * verify_connection(h, p)  -> bool   (GET /api/info health probe)
    * get_connection(device_id)-> ConnectionProfile (raises on unreachable remote)
    * forward_action(profile, endpoint, payload) -> dict

Existing helpers (is_local, post, get, verify_device_info, list_devices,
WindowsConnection, DeviceInfo, ConnectionMode) are retained for the
Phase 1-A..1-D modules that already import them.
"""
# Notes: docs/phone_agent/windows/connection.md
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Optional
from urllib import request as _urlreq
from urllib.error import URLError

import requests


# ── Phase 1-E spec API ────────────────────────────────────────────────────────

DEFAULT_REMOTE_PORT = 7860


@dataclass
class ConnectionProfile:
    """Phase 1-E: how the agent reaches a target machine.

    For local mode, host='localhost' and port=0 (sentinel — no socket used).
    For remote mode, host/port point at a Windows Agent Server (WAS).
    """
    host: str
    port: int
    mode: Literal["local", "remote"]


def detect_mode(device_id: Optional[str]) -> ConnectionProfile:
    """Map a device_id string to a ConnectionProfile.

    Rules (per Phase 1-E spec):
        None | "" | "local"        -> local profile
        "host:port"                -> remote profile (parsed)
        "host"                     -> remote profile (default port 7860)
    """
    if device_id is None or device_id.strip().lower() in ("", "local"):
        return ConnectionProfile(host="localhost", port=0, mode="local")

    raw = device_id.strip()
    if raw.startswith("http://"):
        raw = raw[len("http://"):]
    elif raw.startswith("https://"):
        raw = raw[len("https://"):]
    raw = raw.rstrip("/")

    if ":" in raw:
        host, _, port_str = raw.partition(":")
        try:
            port = int(port_str)
        except ValueError:
            port = DEFAULT_REMOTE_PORT
    else:
        host, port = raw, DEFAULT_REMOTE_PORT

    return ConnectionProfile(host=host, port=port, mode="remote")


def verify_connection(host: str, port: int, timeout: float = 3) -> bool:
    """Health-probe a WAS at host:port. Returns True iff reachable + healthy.

    Hits GET /api/info and treats any JSON response containing a 'machine'
    field as healthy. Swallows network/parse errors and returns False —
    DoD requires no exception on unreachable host.
    """
    url = f"http://{host}:{port}/api/info"
    try:
        with _urlreq.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
        return isinstance(data, dict) and "machine" in data
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def get_connection(device_id: Optional[str]) -> ConnectionProfile:
    """Return a ConnectionProfile, verifying remote reachability.

    Raises ConnectionError if a remote target cannot be reached.
    """
    profile = detect_mode(device_id)
    if profile.mode == "remote":
        if not verify_connection(profile.host, profile.port):
            raise ConnectionError(
                f"Cannot reach Windows Agent Server at "
                f"{profile.host}:{profile.port}"
            )
    return profile


def forward_action(
    profile: ConnectionProfile,
    endpoint: str,
    payload: dict[str, Any],
    timeout: float = 10,
) -> dict:
    """POST an action to a remote WAS and return the parsed JSON response.

    `endpoint` is the bare action name (e.g. "click", "type"); the
    "/api/action/" prefix is added automatically. Pass a leading "/" to
    skip the prefix and POST to a custom path.
    """
    if profile.mode != "remote":
        raise ValueError("forward_action requires a remote ConnectionProfile")

    if endpoint.startswith("/"):
        path = endpoint
    else:
        path = f"/api/action/{endpoint.lstrip('/')}"

    url = f"http://{profile.host}:{profile.port}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = _urlreq.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _urlreq.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw else {}


# ── Legacy helpers retained for Phase 1-A..1-D modules ────────────────────────


class ConnectionMode(Enum):
    LOCAL = "local"
    REMOTE = "remote"


@dataclass
class DeviceInfo:
    machine: str
    os: str
    screen_width: int
    screen_height: int
    device_id: str | None = None
    mode: ConnectionMode = ConnectionMode.LOCAL


def is_local(device_id: str | None) -> bool:
    return device_id is None or device_id.strip().lower() in ("", "local")


def get_was_url(device_id: str) -> str:
    if device_id.startswith("http"):
        return device_id.rstrip("/")
    if ":" not in device_id:
        return f"http://{device_id}:{DEFAULT_REMOTE_PORT}"
    return f"http://{device_id}"


def post(device_id: str, path: str, payload: dict[str, Any], timeout: int = 10) -> dict:
    url = get_was_url(device_id) + path
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get(device_id: str, path: str, timeout: int = 10) -> dict:
    url = get_was_url(device_id) + path
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def verify_device_info(device_id: str, timeout: int = 5) -> DeviceInfo:
    """Call GET /api/info on WAS and return machine info. Raises on failure.

    (Renamed from the Phase-1-pre `verify_connection` so the spec name is
    free for the bool-returning health probe above.)
    """
    data = get(device_id, "/api/info", timeout=timeout)
    return DeviceInfo(
        machine=data.get("machine", "unknown"),
        os=data.get("os", "unknown"),
        screen_width=data.get("screen", {}).get("width", 1920),
        screen_height=data.get("screen", {}).get("height", 1080),
        device_id=device_id,
        mode=ConnectionMode.REMOTE,
    )


def list_devices() -> list[DeviceInfo]:
    """Local mode returns one entry representing this machine."""
    import platform
    import socket

    try:
        import mss
        with mss.mss() as sct:
            m = sct.monitors[1]
            w, h = m["width"], m["height"]
    except Exception:
        w, h = 1920, 1080

    return [DeviceInfo(
        machine=socket.gethostname(),
        os=f"{platform.system()} {platform.release()}",
        screen_width=w,
        screen_height=h,
        device_id=None,
        mode=ConnectionMode.LOCAL,
    )]


class WindowsConnection:
    """
    Thin connection wrapper for the Windows Agent Server (WAS).

    Mirrors the ADBConnection / HDCConnection interface used by
    DeviceFactory.get_connection_class() and main.py's --connect CLI flow.

    In local mode (device_id=None / "local") the agent calls pyautogui
    directly — no connection object is needed.  This class handles the
    *remote* case: verifying that a WAS is reachable at a given address.
    """

    def connect(self, address: str) -> tuple[bool, str]:
        """Verify WAS is reachable at address (e.g. '192.168.1.10:7860')."""
        try:
            info = verify_device_info(address, timeout=5)
            return True, (
                f"Connected to {info.machine} ({info.os}), "
                f"screen {info.screen_width}×{info.screen_height}"
            )
        except Exception as exc:
            return False, f"Cannot reach Windows Agent Server at {address}: {exc}"

    def disconnect(self, address: str | None = None) -> tuple[bool, str]:
        """No-op — WAS uses stateless HTTP; nothing to disconnect."""
        return True, "WAS connections are stateless (no explicit disconnect needed)"

    def enable_tcpip(self, port: int, device_id: str | None = None) -> tuple[bool, str]:
        """Not applicable for WAS — it always listens on HTTP."""
        return False, "TCP/IP mode is not applicable for the Windows Agent Server"

    def get_device_ip(self, device_id: str | None = None) -> str | None:
        return None
