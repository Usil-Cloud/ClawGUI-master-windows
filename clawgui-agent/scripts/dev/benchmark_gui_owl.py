"""End-to-end live benchmark for Phase 1-F (Q5-A).

Captures the VS Code 5-state battery, runs each through the live
GUIOwlAdapter pointed at a running run_gui_owl_2b.py wrapper, measures
latency, writes a markdown report.

Acceptance criteria (Q4-B):
  - 5/5 screenshots return a non-fallback ScreenState
  - Each ScreenState has at least one element AND non-empty planned_action
  - Median latency under 30 sec

Usage
-----
    # Wrapper server already running on http://127.0.0.1:8002
    python scripts/dev/benchmark_gui_owl.py

    # Custom endpoint or skip capture (use existing fixtures)
    python scripts/dev/benchmark_gui_owl.py --endpoint http://gpu-rig:8002
    python scripts/dev/benchmark_gui_owl.py --fixtures-dir <path>

This script runs in the project's main venv (it imports 1-A screenshot,
1-F adapter, etc.). The wrapper server runs in the perception venv. Two
separate Python environments by design.
"""
# Notes: docs/scripts/dev/benchmark_gui_owl.py.md
from __future__ import annotations

import argparse
import base64
import datetime
import json
import logging
import pathlib
import statistics
import subprocess
import sys
import time
import urllib.request
from urllib.error import URLError

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import types
from unittest.mock import MagicMock


def _stub_if_missing(name: str, **attrs) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except (ImportError, Exception):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod


_stub_if_missing("openai", OpenAI=MagicMock, AsyncOpenAI=MagicMock)
_stub_if_missing("phone_agent.model.client", ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.model",         ModelClient=MagicMock, ModelConfig=MagicMock)
_stub_if_missing("phone_agent.agent",         PhoneAgent=MagicMock)
_stub_if_missing("phone_agent.agent_ios",     IOSPhoneAgent=MagicMock)

from phone_agent.perception import GUIOwlAdapter, ScreenState  # noqa: E402
from phone_agent.windows.screenshot import Screenshot  # noqa: E402

log = logging.getLogger(__name__)

ACCEPTANCE = {
    "min_elements_per_shot": 1,
    "max_median_latency_sec": 30.0,
    "min_pass_rate": 1.0,    # 5/5
}

PER_STATE_PROMPTS: dict[str, str] = {
    "empty_window":     "Identify the major UI regions of this empty editor window.",
    "welcome_page":     "Identify the action tiles on the Get Started page.",
    "file_tree":        "Identify the file tree panel and the project files visible.",
    "editor_terminal":  "Identify the editor area and the terminal panel.",
    "command_palette":  "Identify the command palette modal and one visible command.",
}


def _check_health(endpoint: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(f"{endpoint}/health", timeout=timeout) as resp:
            body = json.loads(resp.read())
            log.info("wrapper /health: %s", body)
            return bool(body.get("ok"))
    except (URLError, json.JSONDecodeError, OSError) as e:
        log.error("wrapper not reachable at %s: %s", endpoint, e)
        return False


def _load_screenshot_from_png(path: pathlib.Path) -> Screenshot:
    png_bytes = path.read_bytes()
    from PIL import Image
    import io
    with Image.open(io.BytesIO(png_bytes)) as im:
        w, h = im.size
    return Screenshot(
        base64_data=base64.b64encode(png_bytes).decode("ascii"),
        width=w, height=h, mode="full",
    )


def _capture_battery(project_dir: pathlib.Path) -> pathlib.Path:
    log.info("invoking capture_vscode_battery...")
    capture_script = PROJECT_ROOT / "scripts" / "dev" / "capture_vscode_battery.py"
    result = subprocess.run(
        [sys.executable, str(capture_script), "--project-dir", str(project_dir)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        log.error("capture script failed:\nSTDOUT:\n%s\nSTDERR:\n%s",
                  result.stdout, result.stderr)
        raise SystemExit(1)
    # Last line of stdout is the fixtures dir path (printed by the capture script)
    fixtures_dir = pathlib.Path(result.stdout.strip().splitlines()[-1])
    if not fixtures_dir.exists():
        raise SystemExit(f"capture script reported {fixtures_dir} but it doesn't exist")
    return fixtures_dir


STATE_ORDER = ("empty_window", "welcome_page", "file_tree",
               "editor_terminal", "command_palette")


def _run_one(adapter: GUIOwlAdapter, png_path: pathlib.Path,
             state_name: str) -> dict:
    screenshot = _load_screenshot_from_png(png_path)
    prompt = PER_STATE_PROMPTS[state_name]
    t0 = time.monotonic()
    state: ScreenState = adapter.analyze(screenshot, prompt=prompt)
    wall = time.monotonic() - t0
    is_fallback = bool(state.raw_response.get("fallback"))
    return {
        "state_name": state_name,
        "png": str(png_path),
        "wall_latency_sec": round(wall, 3),
        "model_latency_sec": state.raw_response.get("raw", {}).get("latency_sec")
                              if not is_fallback else None,
        "fallback": is_fallback,
        "failed_step": state.raw_response.get("failed_step") if is_fallback else None,
        "elements": [
            {"label": el.label, "bbox": list(el.bbox),
             "confidence": el.confidence, "type": el.element_type}
            for el in state.elements
        ],
        "planned_action": state.planned_action,
        "reflection": state.reflection,
        "raw_model_text": state.raw_response.get("raw", {}).get("model_text", "")[:1000],
    }


def _evaluate(results: list[dict]) -> dict:
    pass_per_shot: list[bool] = []
    latencies_model: list[float] = []
    latencies_wall: list[float] = []
    for r in results:
        ok = (
            not r["fallback"]
            and len(r["elements"]) >= ACCEPTANCE["min_elements_per_shot"]
            and bool(r["planned_action"].strip())
        )
        pass_per_shot.append(ok)
        latencies_wall.append(r["wall_latency_sec"])
        if r["model_latency_sec"] is not None:
            latencies_model.append(r["model_latency_sec"])

    pass_rate = sum(pass_per_shot) / len(pass_per_shot) if pass_per_shot else 0.0
    median_lat = statistics.median(latencies_wall) if latencies_wall else float("inf")
    overall_pass = (
        pass_rate >= ACCEPTANCE["min_pass_rate"]
        and median_lat <= ACCEPTANCE["max_median_latency_sec"]
    )
    return {
        "pass_per_shot": pass_per_shot,
        "pass_rate": pass_rate,
        "median_latency_wall_sec": median_lat,
        "median_latency_model_sec": statistics.median(latencies_model)
                                     if latencies_model else None,
        "overall_pass": overall_pass,
    }


def _write_report(report_path: pathlib.Path, results: list[dict],
                  evaluation: dict, endpoint: str, runtime_label: str,
                  fixtures_dir: pathlib.Path) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    lines.append(f"# GUI-Owl Live Benchmark — {now}")
    lines.append("")
    lines.append(f"- **Endpoint:** `{endpoint}`")
    lines.append(f"- **Runtime label:** `{runtime_label}`")
    lines.append(f"- **Fixtures:** `{fixtures_dir}`")
    lines.append("")
    lines.append("## Acceptance (Q4-B)")
    lines.append("")
    lines.append(f"- Per-shot pass rate: **{evaluation['pass_rate']*100:.0f}%** "
                 f"(target: 100%)")
    lines.append(f"- Median wall-clock latency: **{evaluation['median_latency_wall_sec']:.2f} sec** "
                 f"(target: ≤ 30 sec)")
    if evaluation['median_latency_model_sec'] is not None:
        lines.append(f"- Median model-only latency: "
                     f"{evaluation['median_latency_model_sec']:.2f} sec")
    overall = "✅ PASS" if evaluation["overall_pass"] else "❌ FAIL"
    lines.append(f"- **Overall:** {overall}")
    lines.append("")

    lines.append("## Per-screenshot results")
    lines.append("")
    for r, ok in zip(results, evaluation["pass_per_shot"]):
        mark = "✅" if ok else "❌"
        lines.append(f"### {mark} {r['state_name']}")
        lines.append("")
        lines.append(f"- Screenshot: `{r['png']}`")
        lines.append(f"- Wall latency: {r['wall_latency_sec']:.2f} sec")
        if r['model_latency_sec'] is not None:
            lines.append(f"- Model latency: {r['model_latency_sec']:.2f} sec")
        if r['fallback']:
            lines.append(f"- **FALLBACK** at step `{r['failed_step']}`")
        lines.append(f"- Elements found: {len(r['elements'])}")
        if r['elements']:
            lines.append("- Top elements:")
            for el in r['elements'][:3]:
                lines.append(f"  - `{el['label']}` ({el['type']}, "
                             f"conf {el['confidence']:.2f}, bbox {el['bbox']})")
        lines.append(f"- Planned action: `{r['planned_action'][:200]}`")
        if r['reflection']:
            lines.append(f"- Reflection: `{r['reflection'][:200]}`")
        if r['raw_model_text']:
            lines.append("")
            lines.append("<details><summary>raw model text</summary>")
            lines.append("")
            lines.append("```")
            lines.append(r['raw_model_text'])
            lines.append("```")
            lines.append("</details>")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("report written: %s", report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="GUI-Owl live benchmark (1-F)")
    parser.add_argument("--endpoint", type=str, default="http://127.0.0.1:8002")
    parser.add_argument("--tier", type=str, default="2b",
                        choices=("2b", "7b", "72b", "235b"),
                        help="Tier to send in each /analyze request. The hot-swap "
                             "wrapper loads/evicts based on this value.")
    parser.add_argument("--fixtures-dir", type=str, default=None,
                        help="Reuse an existing fixtures dir; skip the capture step.")
    parser.add_argument("--project-dir", type=str, default=str(PROJECT_ROOT),
                        help="Folder for VS Code state-3 (file_tree) capture.")
    parser.add_argument("--runtime-label", type=str, default="transformers",
                        help="Tag for the report filename + heading "
                             "(e.g. 'transformers', 'vllm', 'cpu-fp16').")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if not _check_health(args.endpoint):
        log.error("Aborting: wrapper server not healthy at %s", args.endpoint)
        log.error("Start it first: "
                  "%USERPROFILE%/.clawgui/venv-perception/Scripts/python "
                  "scripts/dev/run_gui_owl.py --runtime=transformers "
                  f"--default-tier={args.tier} --port=8002")
        sys.exit(1)

    if args.fixtures_dir:
        fixtures_dir = pathlib.Path(args.fixtures_dir)
    else:
        fixtures_dir = _capture_battery(pathlib.Path(args.project_dir))

    adapter = GUIOwlAdapter(model_tier=args.tier, endpoint_url=args.endpoint)

    results: list[dict] = []
    for state in STATE_ORDER:
        png = fixtures_dir / f"{state}.png"
        if not png.exists():
            log.warning("fixture missing for state %s: %s", state, png)
            results.append({
                "state_name": state, "png": str(png),
                "wall_latency_sec": 0.0, "model_latency_sec": None,
                "fallback": True, "failed_step": "fixture_missing",
                "elements": [], "planned_action": "",
                "reflection": "", "raw_model_text": "",
            })
            continue
        results.append(_run_one(adapter, png, state))

    evaluation = _evaluate(results)

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    report_path = (PROJECT_ROOT / "docs" / "features" / "gui_owl_perception"
                   / "benchmarks" / f"{date_str}_vscode_{args.tier}_{args.runtime_label}.md")
    _write_report(report_path, results, evaluation,
                  args.endpoint, f"{args.tier}/{args.runtime_label}", fixtures_dir)

    print("=" * 60)
    print(f"benchmark complete. report: {report_path}")
    print(f"overall: {'PASS' if evaluation['overall_pass'] else 'FAIL'}")
    print(f"  pass_rate: {evaluation['pass_rate']*100:.0f}%")
    print(f"  median wall latency: {evaluation['median_latency_wall_sec']:.2f}s")
    print("=" * 60)
    sys.exit(0 if evaluation["overall_pass"] else 2)


if __name__ == "__main__":
    main()
