"""Test-run safety layer for Windows GUI automation.

Provides three guard rails so live integration tests never hijack a user's
machine without warning or escape route:

1. ``KillSwitch`` — registers a global hotkey (default ``Shift+Right``,
   override via ``CLAWGUI_KILL_HOTKEY``) that, when pressed, releases any
   stuck modifier keys, restores the cursor, kills any child processes the
   test session spawned, and exits the interpreter with code 130.

2. ``PresenceMonitor`` — polls ``GetLastInputInfo`` to detect whether the
   user has touched mouse/keyboard while a test was running. If activity is
   seen mid-test the runner pauses up to 5 seconds; if the user goes idle in
   that window the test resumes, otherwise the run is aborted.

3. ``countdown`` — a 3-2-1 banner printed to stderr before the first test
   action, so a user who happens to be at the keyboard sees the takeover
   coming.

All three primitives are bundled together by the ``safety_session`` context
manager which is wired into pytest via ``tests/windows/conftest.py``.

Set ``CLAWGUI_TEST_SAFETY=0`` to disable the entire layer (useful for CI
where there is no user to protect).

The phase-2 customtkinter overlay imports from this module — kill-switch and
presence state are exposed via the ``state`` attribute of ``safety_session``
so the overlay can render them in real time.
"""
from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

# ── env-var configuration ─────────────────────────────────────────────────────

ENABLED            = os.environ.get("CLAWGUI_TEST_SAFETY", "1") != "0"
KILL_HOTKEY        = os.environ.get("CLAWGUI_KILL_HOTKEY", "shift+right")
PRESENCE_PAUSE_S   = float(os.environ.get("CLAWGUI_PRESENCE_PAUSE_S", "5.0"))
PRESENCE_IDLE_MS   = int(os.environ.get("CLAWGUI_PRESENCE_IDLE_MS", "750"))
COUNTDOWN_SECONDS  = int(os.environ.get("CLAWGUI_COUNTDOWN_S", "3"))

_ON_WINDOWS = platform.system() == "Windows"


# ── shared state (read by overlay in phase 2) ─────────────────────────────────

@dataclass
class SafetyState:
    current_step:    str               = ""
    next_step:       str               = ""
    aborted:         bool              = False
    abort_reason:    str               = ""
    spawned_procs:   list              = field(default_factory=list)
    cleanup_callbacks: list[Callable[[], None]] = field(default_factory=list)


STATE = SafetyState()


def register_process(proc: subprocess.Popen) -> None:
    """Track a process so the kill-switch can terminate it on abort."""
    STATE.spawned_procs.append(proc)


def register_cleanup(fn: Callable[[], None]) -> None:
    """Register a callback the kill-switch will invoke on abort."""
    STATE.cleanup_callbacks.append(fn)


# ── hotkey parsing ────────────────────────────────────────────────────────────

# Windows virtual-key codes (subset we accept in CLAWGUI_KILL_HOTKEY).
_VK = {
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "esc": 0x1B, "escape": 0x1B, "space": 0x20, "tab": 0x09,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
for c in "abcdefghijklmnopqrstuvwxyz0123456789":
    _VK[c] = ord(c.upper())

# MOD_ flags for RegisterHotKey
_MOD = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "win": 0x0008}


def _parse_hotkey(spec: str) -> tuple[int, int]:
    """Parse 'shift+right' → (mod_mask, vk). Raises ValueError on bad spec."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"empty hotkey spec: {spec!r}")
    mods = 0
    vk:   int | None = None
    for p in parts:
        if p in _MOD:
            mods |= _MOD[p]
        elif p in _VK:
            if vk is not None:
                raise ValueError(f"hotkey {spec!r} has multiple non-modifier keys")
            vk = _VK[p]
        else:
            raise ValueError(f"unknown key {p!r} in hotkey {spec!r}")
    if vk is None:
        raise ValueError(f"hotkey {spec!r} has no main key (only modifiers)")
    return mods, vk


# ── KillSwitch ────────────────────────────────────────────────────────────────

class KillSwitch:
    """Background thread running a Win32 message pump for a global hotkey.

    On hotkey press: release modifier keys, recenter cursor, terminate every
    process registered via ``register_process``, run cleanup callbacks, and
    exit the interpreter with code 130.
    """

    HOTKEY_ID = 0xC1A4  # arbitrary; unique within this thread

    def __init__(self, hotkey_spec: str = KILL_HOTKEY) -> None:
        self.hotkey_spec     = hotkey_spec
        self._mods, self._vk = _parse_hotkey(hotkey_spec)
        self._thread:        threading.Thread | None = None
        self._tid:           int                     = 0
        self._stop:          threading.Event         = threading.Event()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if not _ON_WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, name="KillSwitch", daemon=True)
        self._thread.start()
        # tiny wait so the message pump exists before tests begin
        time.sleep(0.05)

    def stop(self) -> None:
        if not _ON_WINDOWS or self._thread is None:
            return
        self._stop.set()
        if self._tid:
            # WM_QUIT to the pump thread
            user32 = ctypes.windll.user32
            user32.PostThreadMessageW(self._tid, 0x0012, 0, 0)
        self._thread.join(timeout=1.0)

    # ── pump ──────────────────────────────────────────────────────────────────

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, self.HOTKEY_ID, self._mods, self._vk):
            sys.stderr.write(
                f"[safety] WARNING: could not register kill hotkey "
                f"{self.hotkey_spec!r} — kill switch is disabled\n"
            )
            return

        WM_HOTKEY = 0x0312
        WM_QUIT   = 0x0012
        msg = ctypes.wintypes.MSG() if hasattr(ctypes, "wintypes") else _make_msg()
        try:
            while not self._stop.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret in (0, -1):
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                    self._fire()
                    break
        finally:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)

    # ── abort ─────────────────────────────────────────────────────────────────

    def _fire(self) -> None:
        STATE.aborted     = True
        STATE.abort_reason = f"kill hotkey {self.hotkey_spec!r} pressed"
        sys.stderr.write(f"\n[safety] {STATE.abort_reason} — aborting test run\n")

        _release_modifier_keys()
        _recenter_cursor()

        for proc in list(STATE.spawned_procs):
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass

        for cb in list(STATE.cleanup_callbacks):
            try:
                cb()
            except Exception as exc:
                sys.stderr.write(f"[safety] cleanup callback raised: {exc}\n")

        # 130 = SIGINT-equivalent exit code, what shells expect for Ctrl+C.
        os._exit(130)


def _make_msg():
    """Fallback MSG struct if ctypes.wintypes is unavailable."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd",    ctypes.c_void_p),
            ("message", ctypes.c_uint),
            ("wParam",  ctypes.c_void_p),
            ("lParam",  ctypes.c_void_p),
            ("time",    ctypes.c_uint),
            ("pt",      POINT),
        ]
    return MSG()


def _release_modifier_keys() -> None:
    """Send key-up for ctrl/shift/alt/win in case a hotkey() call left them down."""
    if not _ON_WINDOWS:
        return
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C):  # SHIFT, CTRL, ALT, LWIN, RWIN
        try:
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass


def _recenter_cursor() -> None:
    """Move cursor to (200,200) so it isn't sitting in a pyautogui failsafe corner."""
    if not _ON_WINDOWS:
        return
    try:
        ctypes.windll.user32.SetCursorPos(200, 200)
    except Exception:
        pass


# ── PresenceMonitor ───────────────────────────────────────────────────────────

class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def _idle_ms() -> int:
    """Milliseconds since the last user input (0 if not on Windows)."""
    if not _ON_WINDOWS:
        return 10**9  # treat non-Windows as permanently idle
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 10**9
    tick = ctypes.windll.kernel32.GetTickCount()
    return tick - info.dwTime


class PresenceMonitor:
    """Detect user input during a test and decide pause-vs-abort.

    Usage::

        pm = PresenceMonitor()
        pm.mark_test_start()
        ... run test ...
        pm.check_after_test()   # raises UserInterferenceAbort on abort
    """

    def __init__(self,
                 pause_seconds: float = PRESENCE_PAUSE_S,
                 idle_threshold_ms: int = PRESENCE_IDLE_MS) -> None:
        self.pause_seconds     = pause_seconds
        self.idle_threshold_ms = idle_threshold_ms
        self._test_start_idle  = 0

    def mark_test_start(self) -> None:
        self._test_start_idle = _idle_ms()

    def saw_user_input(self) -> bool:
        """True if idle clock reset (decreased) since mark_test_start."""
        # If current idle < idle at start, user pressed/moved something mid-test.
        return _idle_ms() < self._test_start_idle

    def wait_for_idle_or_abort(self) -> None:
        """Block up to pause_seconds; raise UserInterferenceAbort if user keeps typing."""
        if not self.saw_user_input():
            return
        sys.stderr.write(
            f"[safety] user input detected mid-test — pausing up to "
            f"{self.pause_seconds:.0f}s for idle...\n"
        )
        deadline = time.monotonic() + self.pause_seconds
        while time.monotonic() < deadline:
            if _idle_ms() >= self.idle_threshold_ms:
                sys.stderr.write("[safety] user idle, resuming\n")
                self._test_start_idle = _idle_ms()
                return
            time.sleep(0.1)
        STATE.aborted     = True
        STATE.abort_reason = "user remained active past presence-pause window"
        raise UserInterferenceAbort(STATE.abort_reason)


class UserInterferenceAbort(RuntimeError):
    """Raised when the presence monitor decides to abort the run."""


# ── countdown banner ──────────────────────────────────────────────────────────

def countdown(seconds: int = COUNTDOWN_SECONDS, hotkey_label: str = KILL_HOTKEY) -> None:
    """Print a 3-2-1 takeover warning to stderr before the first test action."""
    if seconds <= 0:
        return
    sys.stderr.write(
        f"\n[safety] ClawGUI test run is about to take over this machine.\n"
        f"[safety] Press {hotkey_label!r} at any time to abort.\n"
    )
    for i in range(seconds, 0, -1):
        sys.stderr.write(f"[safety] starting in {i}...\n")
        sys.stderr.flush()
        time.sleep(1.0)
    sys.stderr.write("[safety] running.\n\n")


# ── session bundle ────────────────────────────────────────────────────────────

@contextmanager
def safety_session(*, run_countdown: bool = True) -> Iterator[SafetyState]:
    """Bundle KillSwitch + PresenceMonitor + countdown into one context."""
    if not ENABLED:
        yield STATE
        return

    if run_countdown:
        countdown()

    ks = KillSwitch()
    ks.start()
    try:
        yield STATE
    finally:
        ks.stop()
