---
mirrors: tests/windows/test_app_resolver.py
last_updated: 2026-04-25
status: active
---

# test_app_resolver

## Purpose
Tests for the **5-tier `AppResolver`** in `phone_agent/windows/app_resolver.py` — the helper Feature 1-B uses to find an executable from an app name.

## Approach
All tests are mocked / temp-dir based — no Windows required. Verifies each tier in isolation:

1. **Tier 1 static** — `APP_PACKAGES_WINDOWS` config lookup, case-insensitive.
2. **Tier 2 registry** — `winreg` mock returns a path; resolver verifies the .exe exists.
3. **Tier 3 UWP** — `subprocess.run` mock returns JSON from `Get-StartApps`; resolver builds `shell:AppsFolder\<id>` invocation.
4. **Tier 4 dynamic scan** — temp dirs under `%LOCALAPPDATA%` / `%PROGRAMFILES%`; `_find_exe_in_dir` walks one level deep with last-word match.
5. **Tier 5 Start Menu** — sentinel `LaunchCommand(args=[], resolved_path='start_menu')`; integration consumes via `pyautogui` hotkey.

Includes priority-chain tests: tier 1 hit short-circuits; failure cascades through 2 → 3 → 4 → 5; all-tier failure returns `None`.

Helper tests cover `_exe_candidates` (alias map: "Visual Studio Code" → `code.exe`, "Microsoft Edge" → `msedge.exe`) and `_find_exe_in_dir` (exact match preferred, last-word fallback, one-level subfolder search).

## Status
All passing cross-platform.

## Known Bugs
None.

## Linked Docs
- Source: `phone_agent/windows/app_resolver.py`
- Consumer: [test_device.md](test_device.md) (Feature 1-B `launch_app`)
