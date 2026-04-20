"""Windows connection mode detection and remote HTTP client."""
from __future__ import annotations
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests


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
        return f"http://{device_id}:7860"
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


def verify_connection(device_id: str, timeout: int = 5) -> DeviceInfo:
    """Call GET /api/info on WAS and return machine info. Raises on failure."""
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
            info = verify_connection(address, timeout=5)
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
