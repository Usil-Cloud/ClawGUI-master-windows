r"""Windows application resolver -- maps a human app name to a launchable command.

Resolution tiers (tried in order, first hit wins)
--------------------------------------------------
1. Static PATH config  -- system/dev tools whose exe is genuinely on PATH
                          (notepad.exe, calc.exe, code, wt.exe, ...)
2. Registry App Paths  -- HKLM/HKCU Software\Microsoft\Windows\CurrentVersion\App Paths
                          Nearly every Win32 installer registers here, including
                          Discord, Slack, Zoom, Spotify, Chrome, Blender, etc.
3. PowerShell Get-StartApps -- UWP / Microsoft Store apps that have no .exe path
                               Launched via explorer shell:AppsFolder\ AppID
4. Dynamic install scan -- fuzzy-scan %LOCALAPPDATA%, %PROGRAMFILES%, %PROGRAMFILES(X86)%
                           one level deep, matching folder names to the app name
5. Start Menu search   -- last resort: Win key + type + Enter via pyautogui
                          Slow and UI-dependent but catches everything Windows Search indexes

Usage
-----
    from phone_agent.windows.app_resolver import AppResolver

    cmd = AppResolver().resolve("Discord")
    if cmd:
        import subprocess
        subprocess.Popen(cmd.args)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class LaunchCommand:
    """Everything needed to launch an app."""
    args: list          # passed directly to subprocess.Popen
    tier: int           # which tier resolved it (1-5), for logging / telemetry
    resolved_path: str  # human-readable description of what was found


class AppResolver:
    """Resolve a human-readable app name to a LaunchCommand.

    Instantiate once and reuse; resolve() is stateless (no caching so that
    newly-installed apps are picked up between agent steps).
    """

    def resolve(self, app_name: str) -> Optional[LaunchCommand]:
        """Return a LaunchCommand for app_name, or None if all tiers fail."""
        for tier_fn in (
            self._tier1_static,
            self._tier2_registry,
            self._tier3_uwp,
            self._tier4_scan,
            self._tier5_startmenu,
        ):
            result = tier_fn(app_name)
            if result is not None:
                log.debug(
                    "app_resolver: %r resolved via tier %d -> %s",
                    app_name, result.tier, result.resolved_path,
                )
                return result

        log.warning("app_resolver: could not resolve %r via any tier", app_name)
        return None

    # ------------------------------------------------------------------
    # Tier 1 -- static PATH config
    # ------------------------------------------------------------------

    def _tier1_static(self, app_name: str) -> Optional[LaunchCommand]:
        try:
            from phone_agent.config.apps_windows import APP_PACKAGES_WINDOWS
        except ImportError:
            return None

        exe = APP_PACKAGES_WINDOWS.get(app_name) or APP_PACKAGES_WINDOWS.get(app_name.lower())
        if exe:
            return LaunchCommand(args=[exe], tier=1, resolved_path=exe)
        return None

    # ------------------------------------------------------------------
    # Tier 2 -- Windows Registry App Paths
    # ------------------------------------------------------------------

    def _tier2_registry(self, app_name: str) -> Optional[LaunchCommand]:
        """Look up HKLM/HKCU App Paths for common exe name variants."""
        try:
            import winreg
        except ImportError:
            return None  # non-Windows

        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        candidates = _exe_candidates(app_name)

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for exe_name in candidates:
                full_key = f"{key_path}\\{exe_name}"
                try:
                    with winreg.OpenKey(hive, full_key) as k:
                        path, _ = winreg.QueryValueEx(k, "")  # default value = exe path
                        if path and Path(path).exists():
                            return LaunchCommand(
                                args=[str(path)],
                                tier=2,
                                resolved_path=str(path),
                            )
                except (FileNotFoundError, OSError):
                    continue
        return None

    # ------------------------------------------------------------------
    # Tier 3 -- UWP / Microsoft Store apps via Get-StartApps
    # ------------------------------------------------------------------

    def _tier3_uwp(self, app_name: str) -> Optional[LaunchCommand]:
        """Run PowerShell Get-StartApps and fuzzy-match the app name."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-StartApps | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None

            apps = json.loads(result.stdout)
            if isinstance(apps, dict):  # single result comes back as object
                apps = [apps]

            lower = app_name.lower()
            for entry in apps:
                name = entry.get("Name", "")
                if lower in name.lower():
                    app_id = entry.get("AppID", "")
                    if app_id:
                        return LaunchCommand(
                            args=["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                            tier=3,
                            resolved_path=f"shell:AppsFolder\\{app_id}",
                        )
        except Exception:
            log.debug("app_resolver: tier 3 (Get-StartApps) failed", exc_info=True)
        return None

    # ------------------------------------------------------------------
    # Tier 4 -- dynamic scan of common install roots
    # ------------------------------------------------------------------

    def _tier4_scan(self, app_name: str) -> Optional[LaunchCommand]:
        """Scan %LOCALAPPDATA%, %PROGRAMFILES%, %PROGRAMFILES(X86)% for a
        folder whose name fuzzy-matches app_name, then find the main exe."""
        roots = [
            os.environ.get("LOCALAPPDATA", ""),
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMW6432", ""),       # native 64-bit on WOW64
            os.environ.get("PROGRAMFILES(X86)", ""),
        ]
        lower = app_name.lower()

        for root in roots:
            if not root:
                continue
            root_path = Path(root)
            if not root_path.is_dir():
                continue
            try:
                subdirs = [d for d in root_path.iterdir() if d.is_dir()]
            except PermissionError:
                continue

            for d in subdirs:
                if lower in d.name.lower():
                    exe = _find_exe_in_dir(d, app_name)
                    if exe:
                        return LaunchCommand(
                            args=[str(exe)],
                            tier=4,
                            resolved_path=str(exe),
                        )
        return None

    # ------------------------------------------------------------------
    # Tier 5 -- Start Menu search (pyautogui)
    # ------------------------------------------------------------------

    def _tier5_startmenu(self, app_name: str) -> Optional[LaunchCommand]:
        """Open Start Menu, type app name, press Enter.

        Returns a sentinel LaunchCommand with args=[] and tier=5 when
        attempted; the caller should NOT call subprocess.Popen for this tier
        since the launch already happened via pyautogui.
        """
        try:
            import pyautogui
            pyautogui.hotkey("win")
            time.sleep(0.6)
            pyautogui.typewrite(app_name, interval=0.05)
            time.sleep(0.9)
            pyautogui.press("enter")
            return LaunchCommand(args=[], tier=5, resolved_path="start_menu")
        except Exception:
            log.debug("app_resolver: tier 5 (Start Menu) failed", exc_info=True)
        return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _exe_candidates(app_name: str) -> list:
    """Generate likely .exe filenames for an app name.

    e.g. "Visual Studio Code"  ->  ["Visual Studio Code.exe",
                                    "visualstudiocode.exe", "code.exe"]
    """
    base = app_name.strip()
    slug = base.lower().replace(" ", "")
    seen: set = set()
    candidates: list = []
    for name in (f"{base}.exe", f"{slug}.exe"):
        if name not in seen:
            seen.add(name)
            candidates.append(name)
    # common short aliases
    aliases = {
        "visual studio code": "code.exe",
        "vs code": "code.exe",
        "microsoft edge": "msedge.exe",
        "google chrome": "chrome.exe",
        "windows terminal": "wt.exe",
        "command prompt": "cmd.exe",
        "unreal engine": "UnrealEditor.exe",
    }
    alias = aliases.get(base.lower())
    if alias and alias not in candidates:
        candidates.append(alias)
    return candidates


def _find_exe_in_dir(directory: Path, app_name: str) -> Optional[Path]:
    """Return the best exe inside directory for app_name.

    Preference order:
    1. An exe whose stem matches app_name (case-insensitive)
    2. An exe whose stem matches the last word of app_name (e.g. "Discord")
    3. The largest exe in the directory (heuristic: main exe tends to be biggest)
    """
    try:
        exes = list(directory.glob("*.exe"))
        # also check one level deeper (e.g. Discord/app-1.x.y/Discord.exe)
        for sub in directory.iterdir():
            if sub.is_dir():
                exes.extend(sub.glob("*.exe"))
    except (PermissionError, OSError):
        return None

    if not exes:
        return None

    lower = app_name.lower()
    last_word = app_name.split()[-1].lower()

    # exact match on full name
    for exe in exes:
        if exe.stem.lower() == lower:
            return exe
    # last-word match (covers "Discord" from "Discord")
    for exe in exes:
        if exe.stem.lower() == last_word:
            return exe
    # partial match
    for exe in exes:
        if lower in exe.stem.lower():
            return exe

    # fallback: biggest file (usually the main binary)
    try:
        return max(exes, key=lambda p: p.stat().st_size)
    except OSError:
        return exes[0]
