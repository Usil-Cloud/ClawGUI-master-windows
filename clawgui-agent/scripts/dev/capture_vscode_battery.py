"""Capture the 5-screenshot VS Code reference battery (Phase 1-F Q3-A).

Five states, in order:
  1. empty_window      — fresh VS Code launch, no folder open
  2. welcome_page      — Get Started tab visible (default first-run)
  3. file_tree         — explorer expanded with a Python project loaded
  4. editor_terminal   — code in editor + integrated terminal open
  5. command_palette   — command palette modal open over editor

Output: PNGs + .label.txt sibling files at
docs/features/gui_owl_perception/benchmarks/fixtures/<timestamp>/

Usage
-----
    python scripts/dev/capture_vscode_battery.py
    python scripts/dev/capture_vscode_battery.py --project-dir <path>  # for state 3
    python scripts/dev/capture_vscode_battery.py --no-launch           # use already-open VS Code

Reuses (per docs/REUSABLE_BLOCKS.md):
  - app_resolver  : find Code.exe
  - screenshot    : 1-A capture
  - input         : 1-C key chords for state changes
  - safety        : kill switch + presence monitor
"""
# Notes: docs/scripts/dev/capture_vscode_battery.md
from __future__ import annotations

import argparse
import datetime
import logging
import pathlib
import subprocess
import sys
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Stub heavy imports the perception conftest stubs, so the project __init__
# doesn't pull openai etc. when we're just capturing screenshots.
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

from phone_agent.windows.app_resolver import AppResolver  # noqa: E402
from phone_agent.windows.input import hotkey, press_key  # noqa: E402
from phone_agent.windows.screenshot import get_screenshot  # noqa: E402

log = logging.getLogger(__name__)

STATE_LABELS: dict[str, str] = {
    "empty_window": (
        "Fresh VS Code window. Visible regions: title bar, menu bar (File, "
        "Edit, View...), activity bar (left edge), empty editor area, status "
        "bar (bottom). No file tree expanded, no editor content."
    ),
    "welcome_page": (
        "VS Code 'Get Started' / Welcome tab open in the editor area. "
        "Visible: title bar, menu bar, activity bar, the Welcome tab's grid "
        "of action tiles (New File, Open Folder, etc.), status bar."
    ),
    "file_tree": (
        "Explorer (file tree) panel expanded on the left, showing a project "
        "directory with multiple files/folders. Editor area shows whatever "
        "file is selected by default. Activity bar Explorer icon is "
        "highlighted."
    ),
    "editor_terminal": (
        "Source code visible in the editor area, integrated terminal open "
        "below the editor (split horizontally). Both panes visible "
        "simultaneously."
    ),
    "command_palette": (
        "Command palette modal floating near the top-center of the window, "
        "with a search input and a list of commands. Editor area visible "
        "behind the dimmed overlay."
    ),
}


def _decode_to_png(b64_data: str, dest: pathlib.Path) -> None:
    import base64
    dest.write_bytes(base64.b64decode(b64_data))


def _capture(name: str, out_dir: pathlib.Path) -> None:
    log.info("capturing state: %s", name)
    shot = get_screenshot()
    png_path = out_dir / f"{name}.png"
    label_path = out_dir / f"{name}.label.txt"
    _decode_to_png(shot.base64_data, png_path)
    label_path.write_text(STATE_LABELS[name], encoding="utf-8")
    log.info("  -> %s (%dx%d)", png_path.name, shot.width, shot.height)


def _resolve_vscode():
    return AppResolver().resolve("Visual Studio Code") or AppResolver().resolve("Code")


def _launch_vscode():
    cmd = _resolve_vscode()
    if cmd is None:
        log.error("Could not resolve VS Code via AppResolver. Ensure 'code' "
                  "is on PATH or VS Code is registered in Start Menu.")
        return None, None
    log.info("launching VS Code via tier %d: %s", cmd.tier, cmd.resolved_path)
    proc = subprocess.Popen(cmd.args)
    try:
        from phone_agent.windows import safety
        safety.register_process(proc)
    except Exception:
        pass
    return proc, cmd


def _open_folder_via_cli(cmd, project_dir: str) -> bool:
    """Open `project_dir` in the existing VS Code window via its CLI.

    Bypasses the Win32 folder dialog entirely — works for any path, no
    keystroke timing. Tiers 1-2 are direct exe/cmd invocations that accept
    VS Code's CLI args; tier 3 (UWP) goes through `explorer shell:...`,
    which doesn't forward args, so we skip CLI for that.
    """
    if cmd is None or cmd.tier > 2:
        return False
    try:
        subprocess.Popen(list(cmd.args) + ["--reuse-window", project_dir])
        return True
    except OSError as exc:
        log.warning("CLI folder-open failed (%s); falling back to dialog", exc)
        return False


def _open_folder_via_dialog(project_dir: str, state_wait: float) -> None:
    """Fallback: drive the Win32 folder dialog by keystroke.

    Used only when the CLI path isn't available (UWP install, exotic
    resolver tier). Defensive against the autocomplete-eats-Enter bug:
    presses Escape first to clear any modal residue, then Enter twice
    (first dismisses any autocomplete dropdown, second commits).
    """
    from phone_agent.windows.input import type_text
    press_key("escape")
    time.sleep(0.3)
    hotkey("ctrl", "k", "ctrl", "o")
    time.sleep(state_wait)
    type_text(project_dir)
    time.sleep(0.5)
    press_key("enter")
    time.sleep(0.5)
    press_key("enter")


def main() -> None:
    parser = argparse.ArgumentParser(description="VS Code 5-state capture battery")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="Output dir; defaults to a timestamped subdir under "
                             "docs/features/gui_owl_perception/benchmarks/fixtures/")
    parser.add_argument("--project-dir", type=str, default=str(PROJECT_ROOT),
                        help="Folder VS Code opens for state 3 (file_tree). "
                             "Defaults to the project root.")
    parser.add_argument("--no-launch", action="store_true",
                        help="Use an already-open VS Code instance (don't start one).")
    parser.add_argument("--launch-wait", type=float, default=4.0,
                        help="Seconds to wait after launch for VS Code to be ready.")
    parser.add_argument("--state-wait", type=float, default=1.5,
                        help="Seconds to wait between state-change keystrokes and capture.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.out_dir:
        out_dir = pathlib.Path(args.out_dir)
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = (PROJECT_ROOT / "docs" / "features" / "gui_owl_perception"
                   / "benchmarks" / "fixtures" / ts)
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("output dir: %s", out_dir)

    # Wrap in safety session so user can abort with Shift+Right.
    from phone_agent.windows import safety
    with safety.safety_session():

        proc = None
        cmd = None
        if not args.no_launch:
            proc, cmd = _launch_vscode()
            if proc is None:
                sys.exit(1)
            log.info("waiting %.1fs for VS Code to be ready...", args.launch_wait)
            time.sleep(args.launch_wait)
        else:
            cmd = _resolve_vscode()  # for state 3 CLI re-invocation

        # State 1: empty_window — what's on screen right after launch
        _capture("empty_window", out_dir)

        # State 2: welcome_page — VS Code shows Welcome by default; if the
        # user has dismissed it permanently, force-open via Help > Welcome.
        # Use Ctrl+Shift+P -> "Welcome: Open Walkthrough" as a fallback.
        hotkey("ctrl", "shift", "p")
        time.sleep(args.state_wait)
        # The cleanest cross-version trigger is just typing "Welcome" and Enter.
        from phone_agent.windows.input import type_text
        type_text("Welcome: Open Walkthrough")
        time.sleep(0.5)
        press_key("enter")
        time.sleep(args.state_wait)
        _capture("welcome_page", out_dir)

        # State 3: file_tree — open the project folder.
        # Prefer VS Code's CLI over driving the Win32 folder dialog: the
        # dialog's path-textbox autocomplete eats the first Enter (treating
        # it as "navigate into") and leaves the dialog open, which then
        # consumes state 4's Quick-Open keystrokes.
        opened_via_cli = _open_folder_via_cli(cmd, args.project_dir)
        if not opened_via_cli:
            log.info("CLI folder-open unavailable (tier=%s); using dialog fallback",
                     getattr(cmd, "tier", None))
            _open_folder_via_dialog(args.project_dir, args.state_wait)
        time.sleep(max(args.state_wait, 3.0))  # folder load can be slow
        # Force-show the explorer just in case.
        hotkey("ctrl", "shift", "e")
        time.sleep(args.state_wait)
        _capture("file_tree", out_dir)

        # State 4: editor_terminal — open a file + the integrated terminal.
        # Defensive Escape clears any lingering modal (palette, dialog
        # remnants) before Quick Open, so README.md never lands in the
        # wrong textbox.
        press_key("escape")
        time.sleep(0.3)
        hotkey("ctrl", "p")  # quick open
        time.sleep(args.state_wait)
        type_text("README.md")
        time.sleep(0.3)
        press_key("enter")
        time.sleep(args.state_wait)
        # `Ctrl+`` toggles the integrated terminal. We send "grave" via input.py.
        hotkey("ctrl", "grave")
        time.sleep(args.state_wait)
        _capture("editor_terminal", out_dir)

        # State 5: command_palette
        hotkey("ctrl", "shift", "p")
        time.sleep(args.state_wait)
        _capture("command_palette", out_dir)

        # Close palette and (optionally) the VS Code we launched.
        press_key("escape")
        time.sleep(0.3)

        if proc is not None and proc.poll() is None:
            log.info("closing the VS Code instance we launched")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    log.info("done. fixtures: %s", out_dir)
    print(str(out_dir))


if __name__ == "__main__":
    main()
