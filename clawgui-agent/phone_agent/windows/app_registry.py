"""PID-scoped app registry — distinguish test-owned apps from user apps.

Solves two problems documented in
``docs/features/multi_app_integration/bugs.md``:

* **Bug 3** — re-running a test that calls ``subprocess.Popen`` for an app
  spawns a fresh instance every time, even when a previous run's instance is
  still alive. The persistent JSON registry lets a follow-up run discover and
  reuse the alive PID instead of spawning again.

* **Bug 4** — name-based teardown (``find hwnd whose title contains "Visual
  Studio Code" → close``) can hit windows the user owned, destroying unsaved
  work. Every teardown path here is gated by ``is_owned(pid)`` — adopted and
  unknown PIDs are never killed.

Two PID classes
---------------
* **OWNED** — spawned by ``spawn()`` *or* alive PIDs reloaded from the
  persistent file. Eligible to be closed at teardown.
* **ADOPTED** — pre-existing user processes registered via ``adopt_running``
  or ``adopt_pid``. The test session may *use* their windows but must never
  close them. Configured via ``CLAWGUI_ADOPT_APPS`` env var or
  ``~/.clawgui/adopt.json``.

Phase 2 GUI-vision will eventually replace explicit adoption with
screenshot-based detection of the user's open apps; until then the
config-and-prompt path lives here.
"""
# Notes: docs/features/multi_app_integration/app_registry.md
from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_ON_WINDOWS = platform.system() == "Windows"

# ── persistent + in-memory state ─────────────────────────────────────────────

REGISTRY_DIR  = Path.home() / ".clawgui"
REGISTRY_FILE = REGISTRY_DIR / "app_registry.json"
ADOPT_FILE    = REGISTRY_DIR / "adopt.json"

_lock = threading.Lock()


@dataclass
class _Entry:
    pid: int
    exe: str          # base exe filename, lowercase, e.g. "code.exe"
    spawned_at: float # epoch seconds
    label: str = ""   # caller-supplied label, e.g. "Discord"


@dataclass
class _State:
    owned:   dict[int, _Entry] = field(default_factory=dict)
    adopted: dict[int, _Entry] = field(default_factory=dict)


_STATE = _State()


# ── pywin32-backed primitives (best-effort, never raise) ─────────────────────

def _is_pid_alive(pid: int) -> bool:
    if not _ON_WINDOWS or pid <= 0:
        return False
    try:
        import win32api, win32con  # type: ignore
        STILL_ACTIVE = 259
        h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            return win32api.GetExitCodeProcess(h) == STILL_ACTIVE
        finally:
            win32api.CloseHandle(h)
    except Exception:
        return False


def _exe_basename_for_pid(pid: int) -> str:
    """Return lowercase base exe name for *pid*, or '' on any failure."""
    if not _ON_WINDOWS or pid <= 0:
        return ""
    try:
        import win32api, win32con, win32process  # type: ignore
        h = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.PROCESS_VM_READ,
            False, pid,
        )
        try:
            full = win32process.GetModuleFileNameEx(h, 0)
        finally:
            win32api.CloseHandle(h)
        return Path(full).name.lower()
    except Exception:
        # PROCESS_VM_READ may be denied; fall back to QueryFullProcessImageName
        try:
            import win32api, win32con, win32process  # type: ignore
            h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                full = win32process.GetModuleFileNameEx(h, 0)  # may still fail
            finally:
                win32api.CloseHandle(h)
            return Path(full).name.lower()
        except Exception:
            return ""


def pid_for_hwnd(hwnd: int) -> int:
    """Resolve owning PID of *hwnd*; 0 on failure."""
    if not _ON_WINDOWS or not hwnd:
        return 0
    try:
        import win32process  # type: ignore
        return int(win32process.GetWindowThreadProcessId(hwnd)[1] or 0)
    except Exception:
        return 0


def _enum_pids() -> list[int]:
    if not _ON_WINDOWS:
        return []
    try:
        import win32process  # type: ignore
        return [int(p) for p in win32process.EnumProcesses()]
    except Exception:
        return []


# ── persistence ──────────────────────────────────────────────────────────────

def _load_registry_file() -> list[_Entry]:
    try:
        if not REGISTRY_FILE.exists():
            return []
        raw = json.loads(REGISTRY_FILE.read_text())
        return [
            _Entry(int(e["pid"]), str(e["exe"]).lower(),
                   float(e.get("spawned_at", 0)), str(e.get("label", "")))
            for e in raw.get("owned", [])
            if isinstance(e, dict) and "pid" in e and "exe" in e
        ]
    except Exception:
        return []


def _save_registry_file() -> None:
    try:
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        alive = [
            {"pid": e.pid, "exe": e.exe, "spawned_at": e.spawned_at, "label": e.label}
            for e in _STATE.owned.values() if _is_pid_alive(e.pid)
        ]
        REGISTRY_FILE.write_text(json.dumps({"owned": alive}, indent=2))
    except Exception:
        pass


def _load_adopt_targets() -> list[str]:
    """Lowercase exe names the user has marked for adoption."""
    targets: list[str] = []
    env = os.environ.get("CLAWGUI_ADOPT_APPS", "")
    if env:
        targets += [s.strip().lower() for s in env.split(",") if s.strip()]
    try:
        if ADOPT_FILE.exists():
            raw = json.loads(ADOPT_FILE.read_text())
            for s in raw.get("adopt", []):
                if isinstance(s, str) and s.strip():
                    targets.append(s.strip().lower())
    except Exception:
        pass
    return list(dict.fromkeys(targets))  # de-dup, preserve order


# ── public API ───────────────────────────────────────────────────────────────

def reload_owned_from_disk() -> list[int]:
    """Repopulate OWNED with alive PIDs from the persistent file.

    Call this once at session setup before deciding whether to spawn.
    Returns the list of alive PIDs that were re-registered.
    """
    alive: list[int] = []
    with _lock:
        for entry in _load_registry_file():
            if _is_pid_alive(entry.pid):
                _STATE.owned[entry.pid] = entry
                alive.append(entry.pid)
    return alive


def find_alive_owned_pid(exe_substr: str) -> int:
    """First alive OWNED PID whose exe name contains *exe_substr* (case-insensitive)."""
    needle = exe_substr.lower()
    with _lock:
        for entry in list(_STATE.owned.values()):
            if needle in entry.exe and _is_pid_alive(entry.pid):
                return entry.pid
    return 0


def find_adopted_pid(exe_substr: str) -> int:
    needle = exe_substr.lower()
    with _lock:
        for entry in list(_STATE.adopted.values()):
            if needle in entry.exe and _is_pid_alive(entry.pid):
                return entry.pid
    return 0


def adopt_pid(pid: int, label: str = "") -> bool:
    """Mark *pid* as adopted (will never be closed by teardown)."""
    if not _is_pid_alive(pid):
        return False
    exe = _exe_basename_for_pid(pid)
    with _lock:
        _STATE.adopted[pid] = _Entry(pid, exe, time.time(), label)
    return True


def adopt_running(exe_substr: str, label: str = "") -> list[int]:
    """Scan all running processes, adopt every PID whose exe matches *exe_substr*."""
    needle = exe_substr.lower()
    adopted: list[int] = []
    for pid in _enum_pids():
        exe = _exe_basename_for_pid(pid)
        if exe and needle in exe and adopt_pid(pid, label or exe):
            adopted.append(pid)
    return adopted


def auto_adopt_from_config() -> list[int]:
    """Load adopt config (env + adopt.json) and adopt every matching running PID."""
    found: list[int] = []
    for target in _load_adopt_targets():
        found.extend(adopt_running(target, label=target))
    return found


def spawn(exe_label: str, args: list[str], **popen_kwargs) -> subprocess.Popen:
    """Popen *args*, register the launcher PID as OWNED, persist to disk."""
    proc = subprocess.Popen(args, **popen_kwargs)
    exe = Path(args[0]).name.lower() if args else exe_label.lower()
    with _lock:
        _STATE.owned[proc.pid] = _Entry(proc.pid, exe, time.time(), exe_label)
    _save_registry_file()
    return proc


def register_hwnd_pid(hwnd: int, label: str = "") -> int:
    """Resolve hwnd → PID and register that PID as OWNED.

    Needed because launchers (e.g. ``code --new-window``) exit immediately and
    the actual window is owned by a different long-lived renderer PID.
    Returns the registered PID, or 0 on failure.
    """
    pid = pid_for_hwnd(hwnd)
    if not pid:
        return 0
    if not _is_pid_alive(pid):
        return 0
    if pid in _STATE.adopted:
        # An adopted window — never demote to owned. Caller is reusing a user app.
        return pid
    exe = _exe_basename_for_pid(pid)
    with _lock:
        _STATE.owned[pid] = _Entry(pid, exe, time.time(), label or exe)
    _save_registry_file()
    return pid


def is_owned(pid: int) -> bool:
    with _lock:
        return pid in _STATE.owned


def is_adopted(pid: int) -> bool:
    with _lock:
        return pid in _STATE.adopted


def safe_close_hwnd(hwnd: int, *, hard_kill_after: float = 0.5) -> str:
    """Close *hwnd* only if its PID is OWNED.

    Returns one of:
      'closed'   — WM_CLOSE accepted within hard_kill_after
      'killed'   — process was terminated as a fallback
      'skipped'  — hwnd belongs to ADOPTED or unknown PID; nothing done
      'noop'     — hwnd invalid / pid resolution failed
    """
    if not _ON_WINDOWS or not hwnd:
        return "noop"
    pid = pid_for_hwnd(hwnd)
    if not pid:
        return "noop"
    if not is_owned(pid):
        return "skipped"
    try:
        import win32api, win32con, win32gui  # type: ignore
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        time.sleep(hard_kill_after)
        if not _is_pid_alive(pid):
            _drop_owned(pid)
            return "closed"
        # Force-terminate — only PID we own
        try:
            h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)
            try:
                win32api.TerminateProcess(h, 1)
            finally:
                win32api.CloseHandle(h)
        except Exception:
            pass
        _drop_owned(pid)
        return "killed"
    except Exception:
        return "noop"


def _drop_owned(pid: int) -> None:
    with _lock:
        _STATE.owned.pop(pid, None)
    _save_registry_file()


def persist() -> None:
    """Flush current OWNED set to disk, dropping dead PIDs."""
    with _lock:
        for pid in [p for p, e in _STATE.owned.items() if not _is_pid_alive(p)]:
            _STATE.owned.pop(pid, None)
    _save_registry_file()


def reset_for_tests() -> None:
    """Wipe in-memory state (used by unit tests). Does NOT touch the file."""
    with _lock:
        _STATE.owned.clear()
        _STATE.adopted.clear()


def snapshot() -> dict:
    """Read-only view for diagnostics."""
    with _lock:
        return {
            "owned":   [vars(e) for e in _STATE.owned.values()],
            "adopted": [vars(e) for e in _STATE.adopted.values()],
        }
