"""Entry point: start the Windows Agent Server on the target PC.

Usage:
    python windows_agent_server.py
    python windows_agent_server.py --port 7860 --host 0.0.0.0
"""
import argparse
import socket
import subprocess
import uvicorn


def _tailscale_ip() -> str:
    """Return this machine's Tailscale IP (100.x.x.x), or empty string if not found."""
    try:
        out = subprocess.check_output(["tailscale", "ip", "-4"], timeout=3, text=True).strip()
        if out.startswith("100."):
            return out
    except Exception:
        pass
    return ""


def main():
    parser = argparse.ArgumentParser(description="Windows Agent Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Bind port (default: 7860)")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload for development")
    args = parser.parse_args()

    ts_ip = _tailscale_ip()
    ts_line = f"  Tailscale:  http://{ts_ip}:{args.port}/api/health" if ts_ip else "  Tailscale:  NOT DETECTED — install and authenticate Tailscale first"

    print(f"Starting Windows Agent Server on {args.host}:{args.port}")
    print(f"  Local:      http://127.0.0.1:{args.port}/api/health")
    print(ts_line)
    print(f"  Docs:       http://127.0.0.1:{args.port}/docs")
    print("  Auth:       Tailscale 100.x.x.x + loopback only")

    uvicorn.run(
        "phone_agent.windows.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
