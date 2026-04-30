"""HTTP wrapper exposing GUI-Owl-1.5-2B-Instruct on the /analyze contract.

Two interchangeable runtimes per Phase 1-F Q2-B:
  --runtime=transformers   (default; tested) — load the model in-process
  --runtime=vllm           (unverified)      — relay to a remote vLLM endpoint

Both runtimes prompt the model for JSON output matching the wire schema in
docs/INTEGRATION_CONTRACT.md and parse best-effort. Free-form text responses
are dumped into `planned_action` with empty elements; the model output is
always preserved in `raw.model_text` so downstream debugging is possible.

Usage
-----
    # transformers (in-process)
    python scripts/dev/run_gui_owl_2b.py --runtime=transformers --port=8002

    # vLLM (remote, OpenAI-compatible)
    python scripts/dev/run_gui_owl_2b.py --runtime=vllm \\
        --base-url http://gpu-rig:8000/v1 --model GUI-Owl-1.5-2B-Instruct \\
        --port=8002

This script must run inside the perception venv (the one created by
setup_gui_owl_env.py). It will refuse to start if torch+CUDA aren't
available for the transformers runtime.
"""
# Notes: docs/scripts/dev/run_gui_owl_2b.md
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import os
import pathlib
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = (
    pathlib.Path(os.path.expanduser("~"))
    / ".clawgui" / "models" / "GUI-Owl-1.5-2B-Instruct"
)

GROUNDING_PROMPT = """\
You are a UI grounding assistant. Look at this screenshot and identify the
visible interactive elements. Respond ONLY with a JSON object in this exact
schema, no prose before or after:

{
  "elements": [
    {"label": "<short element description>",
     "bbox": [x1, y1, x2, y2],
     "confidence": <0.0-1.0>,
     "type": "<button|input|text|icon|menu|other>"}
  ],
  "planned_action": "<one short sentence: what the user should do next>",
  "reflection": "<one short sentence: what's on screen>"
}

User instruction: {user_prompt}
"""

# ----------------------------------------------------------------------
# Best-effort JSON extraction
# ----------------------------------------------------------------------
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def _extract_payload(model_text: str, fallback_action: str) -> dict[str, Any]:
    """Pull a JSON object out of the model's text response. Best-effort:
    on parse failure, dump the raw text into planned_action so the caller
    sees something useful instead of a fallback ScreenState."""
    match = _JSON_BLOCK_RE.search(model_text)
    if match:
        try:
            obj = json.loads(match.group(0))
            obj.setdefault("elements", [])
            obj.setdefault("planned_action", fallback_action)
            obj.setdefault("reflection", "")
            obj.setdefault("raw", {})
            obj["raw"]["model_text"] = model_text
            return obj
        except (json.JSONDecodeError, ValueError) as e:
            log.warning("model JSON parse failed: %s; falling back to text", e)
    return {
        "elements": [],
        "planned_action": model_text.strip()[:500] or fallback_action,
        "reflection": "",
        "raw": {"model_text": model_text, "parse_failed": True},
    }


# ----------------------------------------------------------------------
# Runtime: transformers (in-process)
# ----------------------------------------------------------------------
class TransformersRuntime:

    def __init__(self, model_dir: pathlib.Path):
        import torch  # noqa: PLC0415
        from transformers import AutoModelForImageTextToText, AutoProcessor  # noqa: PLC0415

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA not available inside this venv. The transformers runtime "
                "is GPU-only by design (P1/P2). For CPU fallback, edit this "
                "file to load with device_map='cpu' and torch_dtype=torch.float32."
            )

        log.info("transformers runtime: loading %s ...", model_dir)
        t0 = time.monotonic()
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), trust_remote_code=True,
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            str(model_dir),
            torch_dtype=torch.float16,
            device_map="auto",
            load_in_4bit=True,            # bitsandbytes int4 quantization at load time
            trust_remote_code=True,
        )
        log.info("model loaded in %.1fs", time.monotonic() - t0)

    def infer(self, image_bytes: bytes, user_prompt: str) -> tuple[str, float]:
        from PIL import Image  # noqa: PLC0415

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        msgs = [{"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": GROUNDING_PROMPT.format(
                user_prompt=user_prompt or "describe the screen"
            )},
        ]}]
        text = self.processor.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=False,
        )
        inputs = self.processor(
            text=[text], images=[img], return_tensors="pt",
        ).to(self.model.device)

        t0 = time.monotonic()
        out = self.model.generate(**inputs, max_new_tokens=512, do_sample=False)
        latency = time.monotonic() - t0

        # Strip the prompt prefix from the decode so we only see the model's
        # generation, not the echoed instructions.
        gen_ids = out[0][inputs["input_ids"].shape[1]:]
        decoded = self.processor.decode(gen_ids, skip_special_tokens=True)
        return decoded, latency


# ----------------------------------------------------------------------
# Runtime: vLLM (relay to remote OpenAI-compatible endpoint) — UNVERIFIED
# ----------------------------------------------------------------------
class VLLMRuntime:

    def __init__(self, base_url: str, model_name: str, api_key: str = "EMPTY"):
        from openai import OpenAI  # noqa: PLC0415
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        log.info("vLLM runtime: relaying to %s (model=%s)", base_url, model_name)

    def infer(self, image_bytes: bytes, user_prompt: str) -> tuple[str, float]:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:image/png;base64,{b64}"
        t0 = time.monotonic()
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": GROUNDING_PROMPT.format(
                    user_prompt=user_prompt or "describe the screen"
                )},
            ]}],
            max_tokens=512, temperature=0.0,
        )
        latency = time.monotonic() - t0
        text = completion.choices[0].message.content or ""
        return text, latency


# ----------------------------------------------------------------------
# HTTP layer (mirrors mock_gui_owl_server, but now with a real backend)
# ----------------------------------------------------------------------
def _make_handler(runtime):
    class _Handler(BaseHTTPRequestHandler):

        def log_message(self, fmt: str, *args: Any) -> None:
            log.info("http: " + fmt, *args)

        def do_GET(self):
            if self.path == "/health":
                self._json(200, {"ok": True, "runtime": type(runtime).__name__})
                return
            self.send_error(404)

        def do_POST(self):
            if self.path != "/analyze":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            ctype = self.headers.get("Content-Type", "")
            body = self.rfile.read(length) if length else b""
            if not ctype.startswith("multipart/form-data"):
                self.send_error(400, f"expected multipart, got {ctype!r}")
                return

            image_bytes, prompt = _parse_multipart(body, ctype)
            if not image_bytes:
                self.send_error(400, "no 'image' part in multipart body")
                return

            try:
                model_text, latency = runtime.infer(image_bytes, prompt)
            except Exception as e:  # noqa: BLE001
                log.exception("inference failed")
                self._json(500, {
                    "error": f"{type(e).__name__}: {e}",
                    "runtime": type(runtime).__name__,
                })
                return

            payload = _extract_payload(model_text,
                                       fallback_action="describe the screen")
            payload.setdefault("raw", {})
            payload["raw"]["latency_sec"] = round(latency, 3)
            payload["raw"]["runtime"] = type(runtime).__name__
            self._json(200, payload)

        def _json(self, status: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def _parse_multipart(body: bytes, content_type: str) -> tuple[bytes | None, str]:
    """Tiny multipart parser for our 'image' + 'prompt' + 'tier' fields.
    We do not depend on email.parser or python-multipart — keeping the wrapper
    free of extra deps.
    """
    m = re.search(r"boundary=(.+?)(?:;|$)", content_type)
    if not m:
        return None, ""
    boundary = m.group(1).strip().strip('"').encode()
    sep = b"--" + boundary
    parts = body.split(sep)
    image: bytes | None = None
    prompt = ""
    for part in parts:
        if not part or part in (b"--\r\n", b"--", b"\r\n--\r\n"):
            continue
        head_end = part.find(b"\r\n\r\n")
        if head_end == -1:
            continue
        headers = part[:head_end].decode("latin-1", errors="replace")
        content = part[head_end + 4:]
        # strip trailing CRLF before the next boundary marker
        if content.endswith(b"\r\n"):
            content = content[:-2]
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue
        name = name_match.group(1)
        if name == "image":
            image = content
        elif name == "prompt":
            prompt = content.decode("utf-8", errors="replace").strip()
    return image, prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="GUI-Owl-1.5-2B HTTP wrapper")
    parser.add_argument("--runtime", choices=("transformers", "vllm"),
                        default="transformers")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--model-dir", type=str, default=str(DEFAULT_MODEL_DIR),
                        help="Local path to the model (transformers runtime only)")
    parser.add_argument("--base-url", type=str, default=None,
                        help="vLLM base URL, e.g. http://gpu-rig:8000/v1")
    parser.add_argument("--vllm-model", type=str, default="GUI-Owl-1.5-2B-Instruct",
                        help="Model name registered in the vLLM server")
    parser.add_argument("--vllm-api-key", type=str, default="EMPTY")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.runtime == "transformers":
        runtime = TransformersRuntime(pathlib.Path(args.model_dir))
    else:
        if not args.base_url:
            raise SystemExit("--base-url is required for --runtime=vllm")
        runtime = VLLMRuntime(args.base_url, args.vllm_model, args.vllm_api_key)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), _make_handler(runtime))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(
        f"gui-owl wrapper listening on http://127.0.0.1:{args.port}/analyze "
        f"(runtime={args.runtime}, Ctrl+C to stop)",
        flush=True,
    )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
