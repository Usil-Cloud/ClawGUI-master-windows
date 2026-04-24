"""Tests for phone_agent/windows/app_resolver.py

Test structure
--------------
Unit tests (MockedResolverTests)
    All five resolver tiers tested in isolation using sys.modules patching
    and temp directories.  Runs on any OS -- no Windows dependencies needed.

Run:
    pytest tests/windows/test_app_resolver.py -v -k "not Integration"
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Pre-stub Windows-only modules so app_resolver imports cleanly on Linux
# ---------------------------------------------------------------------------

def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]

_stub("win32gui",
    GetForegroundWindow=lambda: 0,
    GetWindowText=lambda h: "",
)
_stub("winreg",
    HKEY_LOCAL_MACHINE=0x80000002,
    HKEY_CURRENT_USER=0x80000001,
    OpenKey=MagicMock(side_effect=FileNotFoundError),
    QueryValueEx=MagicMock(return_value=("", 1)),
)
_stub("pyautogui",
    hotkey=lambda *a: None,
    typewrite=lambda *a, **kw: None,
    press=lambda *a: None,
)
_stub("phone_agent.windows.connection",
    is_local=lambda device_id: True,
    post=lambda *a, **kw: {},
    ConnectionMode=object,
    DeviceInfo=object,
    WindowsConnection=object,
    verify_connection=lambda *a, **kw: True,
    list_devices=lambda: [],
)

# Minimal apps_windows stub (Tier 1 config used by resolver)
_stub("phone_agent.config.apps_windows",
    APP_PACKAGES_WINDOWS={
        "Notepad": "notepad.exe",
        "notepad": "notepad.exe",
        "Calculator": "calc.exe",
    }
)

# Ensure phone_agent package stubs exist
for _pkg in ("phone_agent", "phone_agent.windows", "phone_agent.config"):
    if _pkg not in sys.modules:
        sys.modules[_pkg] = types.ModuleType(_pkg)

from phone_agent.windows.app_resolver import (  # noqa: E402
    AppResolver, LaunchCommand, _exe_candidates, _find_exe_in_dir,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_winreg_mock(path_value: str):
    """Return a winreg mock whose OpenKey context manager yields a key that
    returns path_value from QueryValueEx."""
    key_ctx = MagicMock()
    key_ctx.__enter__ = MagicMock(return_value=key_ctx)
    key_ctx.__exit__ = MagicMock(return_value=False)

    winreg_mod = MagicMock()
    winreg_mod.HKEY_LOCAL_MACHINE = 0x80000002
    winreg_mod.HKEY_CURRENT_USER  = 0x80000001
    winreg_mod.OpenKey.return_value = key_ctx
    winreg_mod.QueryValueEx.return_value = (path_value, 1)
    return winreg_mod


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestExeCandidates(unittest.TestCase):
    def test_simple_name(self):
        cands = _exe_candidates("Discord")
        self.assertIn("Discord.exe", cands)
        self.assertIn("discord.exe", cands)

    def test_multi_word_with_alias(self):
        cands = _exe_candidates("Visual Studio Code")
        self.assertIn("code.exe", cands)

    def test_microsoft_edge_alias(self):
        cands = _exe_candidates("Microsoft Edge")
        self.assertIn("msedge.exe", cands)

    def test_no_duplicate_candidates(self):
        cands = _exe_candidates("code")
        self.assertEqual(len(cands), len(set(cands)))


class TestFindExeInDir(unittest.TestCase):
    def test_exact_match_preferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "other.exe").write_bytes(b"x")
            (d / "Discord.exe").write_bytes(b"xx")
            result = _find_exe_in_dir(d, "Discord")
            self.assertEqual(result.name, "Discord.exe")

    def test_last_word_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "Update.exe").write_bytes(b"x")
            (d / "Discord.exe").write_bytes(b"xx")
            result = _find_exe_in_dir(d, "Discord")
            self.assertEqual(result.name, "Discord.exe")

    def test_searches_one_level_deep(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sub = d / "app-1.2.3"
            sub.mkdir()
            (sub / "Discord.exe").write_bytes(b"abc")
            result = _find_exe_in_dir(d, "Discord")
            self.assertIsNotNone(result)
            self.assertEqual(result.name, "Discord.exe")

    def test_returns_none_for_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _find_exe_in_dir(Path(tmp), "Discord")
            self.assertIsNone(result)


class MockedResolverTests(unittest.TestCase):

    # -- Tier 1: static config -----------------------------------------------

    def test_tier1_known_app_resolves(self):
        resolver = AppResolver()
        cmd = resolver._tier1_static("Notepad")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.tier, 1)
        self.assertEqual(cmd.args, ["notepad.exe"])

    def test_tier1_case_insensitive(self):
        cmd = AppResolver()._tier1_static("notepad")
        self.assertIsNotNone(cmd)

    def test_tier1_unknown_app_returns_none(self):
        cmd = AppResolver()._tier1_static("Discord")
        self.assertIsNone(cmd)

    # -- Tier 2: registry ----------------------------------------------------

    def test_tier2_registry_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "Discord.exe"
            fake_exe.write_bytes(b"fake")

            winreg_mock = _make_winreg_mock(str(fake_exe))
            with patch.dict("sys.modules", {"winreg": winreg_mock}):
                cmd = AppResolver()._tier2_registry("Discord")

        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.tier, 2)
        self.assertEqual(cmd.args[0], str(fake_exe))

    def test_tier2_registry_miss_returns_none(self):
        winreg_mod = MagicMock()
        winreg_mod.HKEY_LOCAL_MACHINE = 0x80000002
        winreg_mod.HKEY_CURRENT_USER  = 0x80000001
        winreg_mod.OpenKey.side_effect = FileNotFoundError
        with patch.dict("sys.modules", {"winreg": winreg_mod}):
            cmd = AppResolver()._tier2_registry("NonExistentApp")
        self.assertIsNone(cmd)

    def test_tier2_skipped_on_import_error(self):
        # Simulate non-Windows where winreg does not exist
        with patch.dict("sys.modules", {"winreg": None}):
            cmd = AppResolver()._tier2_registry("Discord")
        self.assertIsNone(cmd)

    # -- Tier 3: UWP / Get-StartApps ----------------------------------------

    def test_tier3_uwp_hit(self):
        import json
        fake_apps = [
            {"Name": "Xbox Game Bar", "AppID": "Microsoft.XboxGamingOverlay_x!App"},
            {"Name": "Discord", "AppID": "com.discord.Discord_xyz!App"},
        ]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(fake_apps)

        with patch("phone_agent.windows.app_resolver.subprocess.run", return_value=mock_result):
            cmd = AppResolver()._tier3_uwp("Discord")

        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.tier, 3)
        self.assertIn("shell:AppsFolder", cmd.args[1])
        self.assertIn("com.discord.Discord_xyz!App", cmd.args[1])

    def test_tier3_no_match_returns_none(self):
        import json
        fake_apps = [{"Name": "Xbox Game Bar", "AppID": "Microsoft.XboxGamingOverlay_x!App"}]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(fake_apps)

        with patch("phone_agent.windows.app_resolver.subprocess.run", return_value=mock_result):
            cmd = AppResolver()._tier3_uwp("Discord")

        self.assertIsNone(cmd)

    def test_tier3_powershell_error_returns_none(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("phone_agent.windows.app_resolver.subprocess.run", return_value=mock_result):
            cmd = AppResolver()._tier3_uwp("Discord")

        self.assertIsNone(cmd)

    # -- Tier 4: dynamic scan ------------------------------------------------

    def test_tier4_scan_finds_app_in_localappdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "Discord"
            app_dir.mkdir()
            (app_dir / "Discord.exe").write_bytes(b"fake_exe_content")

            with patch.dict("os.environ", {"LOCALAPPDATA": tmp,
                                           "PROGRAMFILES": "",
                                           "PROGRAMW6432": "",
                                           "PROGRAMFILES(X86)": ""}):
                cmd = AppResolver()._tier4_scan("Discord")

        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.tier, 4)
        self.assertTrue(cmd.args[0].endswith("Discord.exe"))

    def test_tier4_scan_miss_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Empty directory -- no matching subfolder
            with patch.dict("os.environ", {"LOCALAPPDATA": tmp,
                                           "PROGRAMFILES": "",
                                           "PROGRAMW6432": "",
                                           "PROGRAMFILES(X86)": ""}):
                cmd = AppResolver()._tier4_scan("SomeObscureApp")
        self.assertIsNone(cmd)

    # -- Tier 5: Start Menu --------------------------------------------------

    def test_tier5_startmenu_returns_sentinel(self):
        pyautogui_mock = MagicMock()
        with patch.dict("sys.modules", {"pyautogui": pyautogui_mock}):
            cmd = AppResolver()._tier5_startmenu("Discord")

        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.tier, 5)
        self.assertEqual(cmd.args, [])
        self.assertEqual(cmd.resolved_path, "start_menu")

    def test_tier5_pyautogui_exception_returns_none(self):
        pyautogui_mock = MagicMock()
        pyautogui_mock.hotkey.side_effect = Exception("no display")
        with patch.dict("sys.modules", {"pyautogui": pyautogui_mock}):
            cmd = AppResolver()._tier5_startmenu("Discord")
        self.assertIsNone(cmd)

    # -- Full resolve() priority chain ---------------------------------------

    def test_resolve_prefers_tier1_over_registry(self):
        """Tier 1 hit should short-circuit; registry should never be called."""
        resolver = AppResolver()
        with patch.object(resolver, "_tier2_registry") as mock_reg:
            cmd = resolver.resolve("Notepad")
        mock_reg.assert_not_called()
        self.assertEqual(cmd.tier, 1)

    def test_resolve_falls_through_to_tier4(self):
        """When tier 1/2/3 all miss, tier 4 should be tried."""
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "Blender"
            app_dir.mkdir()
            (app_dir / "Blender.exe").write_bytes(b"blender_binary")

            winreg_mod = MagicMock()
            winreg_mod.HKEY_LOCAL_MACHINE = 0x80000002
            winreg_mod.HKEY_CURRENT_USER  = 0x80000001
            winreg_mod.OpenKey.side_effect = FileNotFoundError

            ps_result = MagicMock()
            ps_result.returncode = 1
            ps_result.stdout = ""

            with patch.dict("sys.modules", {"winreg": winreg_mod}), \
                 patch("phone_agent.windows.app_resolver.subprocess.run", return_value=ps_result), \
                 patch.dict("os.environ", {"LOCALAPPDATA": tmp,
                                           "PROGRAMFILES": "",
                                           "PROGRAMW6432": "",
                                           "PROGRAMFILES(X86)": ""}):
                cmd = AppResolver().resolve("Blender")

        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.tier, 4)

    def test_resolve_returns_none_when_all_tiers_fail(self):
        winreg_mod = MagicMock()
        winreg_mod.HKEY_LOCAL_MACHINE = 0x80000002
        winreg_mod.HKEY_CURRENT_USER  = 0x80000001
        winreg_mod.OpenKey.side_effect = FileNotFoundError

        ps_result = MagicMock()
        ps_result.returncode = 1
        ps_result.stdout = ""

        pyautogui_mock = MagicMock()
        pyautogui_mock.hotkey.side_effect = Exception("no display")

        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict("sys.modules", {"winreg": winreg_mod, "pyautogui": pyautogui_mock}), \
             patch("phone_agent.windows.app_resolver.subprocess.run", return_value=ps_result), \
             patch.dict("os.environ", {"LOCALAPPDATA": tmp,
                                       "PROGRAMFILES": "",
                                       "PROGRAMW6432": "",
                                       "PROGRAMFILES(X86)": ""}):
            cmd = AppResolver().resolve("__totally_unknown_app__")

        self.assertIsNone(cmd)


if __name__ == "__main__":
    unittest.main()
