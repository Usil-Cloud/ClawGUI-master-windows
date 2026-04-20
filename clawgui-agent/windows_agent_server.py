"""Entry point: start the Windows Agent Server on the target PC.

Usage:
    python windows_agent_server.py
    python windows_agent_server.py --port 7860 --host 0.0.0.0
"""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Windows Agent Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Bind port (default: 7860)")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload for development")
    args = parser.parse_args()

    print(f"Starting Windows Agent Server on {args.host}:{args.port}")
    print("  REST API: http://localhost:{args.port}/api/")
    print("  MCP:      http://localhost:{args.port}/mcp")
    print("  Docs:     http://localhost:{args.port}/docs")

    uvicorn.run(
        "phone_agent.windows.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
