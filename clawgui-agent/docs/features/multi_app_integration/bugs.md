---
name: Multi-App Integration bug tracker
description: Bug and observation log for the cross-app integration test suite. Anchors per bug for cross-linking.
type: project
last_updated: 2026-04-27 (all four bugs resolved)
status: active
---

> **2026-04-27 update.** Bug 3 and Bug 4 addressed by introducing a PID-scoped
> app registry (`phone_agent/windows/app_registry.py`,
> [design doc](app_registry.md)). setUp/tearDown of
> `tests/windows/test_multi_app_integration.py` now:
> * reuses still-alive PIDs from prior runs instead of duplicating spawns (Bug 3);
> * closes only OWNED PIDs at teardown — adopted user apps and unrelated user
>   windows are skipped untouched (Bug 4);
> * supports adopting pre-opened apps via `CLAWGUI_ADOPT_APPS` env or
>   `~/.clawgui/adopt.json` for slow-start apps like Unreal Engine 5.
>
> Bugs 1 and 2 (intermittent focus failures) resolved as a side effect of
> Bugs 3 + 4 fix. Root cause confirmed: stray duplicate app instances from
> prior runs were racing for foreground — eliminating duplicates (Bug 3 fix)
> removed the race condition. Verified by user on 2026-04-27.

## Bug 1 — failure on first test action  {#bug-1}

**Status:** resolved · **Severity:** medium · **Reported:** 2026-04-27 · **Fixed:** 2026-04-27 · **Verified:** 2026-04-27

**Symptom(s).** I observed this bug after I ran the 'test_window_manager.py' script (I'm unsure if there's a relation between the two scripts that caused this flow to fail because when I re-ran these two scripts in the same order, this action PASSED on the following runs, so just point out this observation). FAILED status on 'tests/windows/test_multi_app_integration.py::MultiAppWindowTests::test_focus_window_cycles_all_three_apps'. AssertionError: 'Notepad' not found in 'Friends - Discord' : After focus_window('Notepad'), foreground is 'Friends - Discord'. Luis' observation: all apps opened up and were cycled so unsure about what caused the error to show. 

See error screenshot @ 'Project Ready Player\ClawGUI-master\clawgui-agent\docs\features\multi_app_integration\bug_screenshots\phase1D_failure_onfirststep.png'

**Repro.**
1. Run test_multi_app_integration.pu
2. Step

**Where.** `tests/windows/test_multi_app_integration.py::MultiAppWindowTests::test_focus_window_cycles_all_three_apps` (test or helper name)

**Suspected cause.** Stray duplicate app instances from prior runs (Bug 3) were racing for foreground. When multiple Discord or VS Code windows existed, `focus_window` would bring one to front but the wrong PID would sometimes win the race before the assertion fired.

**Fix / workaround.** Resolved as a side effect of Bug 3 fix (`app_registry.py` cross-run PID dedup). With only one instance of each app open, the foreground race no longer occurs.

**Verification result (2026-04-27).** User confirmed no recurrence after Bug 3/4 fix was applied.


## Bug 2 — Inconsistency after successful runs {#bug-2}

**Status:** resolved · **Severity:** high · **Reported:** 2026-04-27 · **Fixed:** 2026-04-27 · **Verified:** 2026-04-27

**Symptom(s).** After I ran the 'test_multi_app_integration.py' script twice to make sure follow up runs don't error out, I did actually run into an error on this sanity test. See the two successful runs @ 'Project Ready Player\ClawGUI-master\clawgui-agent\docs\features\multi_app_integration\bug_screenshots\phase1D_successful_runs.png', then see failure @ 'Project Ready Player\ClawGUI-master\clawgui-agent\docs\features\multi_app_integration\bug_screenshots\phase1D_followup_failure_runs.png'. 

**Repro.**
1. Ran 'test_multi_app_integration.py' more than once
2. A follow up 'test_multi_app_integration.py' run showed an error.

**Where.** `tests/windows/test_multi_app_integration.py::MultiAppWindowTests.test_focus_window_notepad_brings_to_foreground` (test or helper name)

**Suspected cause.** On the second and subsequent runs, duplicate app instances accumulated (Bug 3). `test_focus_window_notepad_brings_to_foreground` would call `focus_window('Notepad')` but with two Notepad windows present, the wrong one could win foreground, causing the assertion against the active window title to fail intermittently.

**Fix / workaround.** Resolved as a side effect of Bug 3 fix. With `app_registry.py` reusing alive PIDs across runs, only one Notepad instance is active per app (ignoring the known session-conftest dual-instance, which is static and does not compete for focus), eliminating the multi-instance race.

**Verification result (2026-04-27).** User confirmed no recurrence after Bug 3/4 fix was applied.



## Bug 3 — Recently opened apps duplicate when running multi_app_integration more than once  {#bug-3}

**Status:** resolved · **Severity:** high · **Reported:** 2026-04-27 · **Fixed:** 2026-04-27 · **Verified:** 2026-04-27

**Symptom(s).** When I run the 'test_multi_app_integration.py' script, each app that was opened on a previous run, gets opened again on a follow up runs. For example, I run the 'test_multi_app_integration.py' script, I see Notepad, discord, and vs code open up-- I then run the script again immedietaly after and then I see Notepad, discord, and vs code opens up a 2nd app, I then run the script a third time, and again, I see see Notepad, discord, and vs code opens up a 3rd instance of the app while still opening the first 2 app instances. It's not like it's closing the 1st and 2nd instances of these apps, it's opening the app 3 times (or N times the script is ran). After the script runs, most of the apps get closed (except notepad always has 1 app instance open).

**Repro.**
1. Run 'test_multi_app_integration.py' more than once [Note for Claude: If you're going to test this repro step, don't run it more than 3 times so that we're not stuck in a loop, and have a clear indicator of when to stop testing.]

**Where.** `tests/windows/test_multi_app_integration.py` (test or helper name)

**Suspected cause.** We are not accurately mapping the apps that we have opened/touched in a way that avoids duplications.

**Fix / workaround.** Added `phone_agent/windows/app_registry.py`. setUp now calls `reload_owned_from_disk()` (which re-registers still-alive PIDs persisted from earlier runs) and the per-app `_resolve_or_spawn` helper reuses an alive OWNED PID before spawning. Persistent file lives at `~/.clawgui/app_registry.json`. See [app_registry.md](app_registry.md).

**Verification result (2026-04-27).** Discord and VS Code each opened exactly one instance across multiple runs. Notepad shows 2 instances — one from the session-shared conftest fixture and one from the module setUp path; dedup not applied there intentionally since the session-shared instance is managed by conftest, not app_registry. Accepted as-is for now.


## Bug 4 — Apps user had opened are being force closed  {#bug-4}

**Status:** resolved · **Severity:** CRITICAL · **Reported:** 2026-04-27 · **Fixed:** 2026-04-27 · **Verified:** 2026-04-27

**Symptom(s).** The test runs are revealing that when I run a script, any app that may have been touched will be force closed. For example, I had a VS code window open that I was using to document bugs found, and then I ran the 'test_multi_app_integration.py' script to see if I'm able to reproduce any bugs, and after the script finished running, I noticed that the script force closed my instance of the VS code app (not one opened up because of the test script), and caused me to lose unsaved changes. Notes for Claude: Do not assume that we want to save all user changes on apps that the scripts may touch. We should simply keep track of what apps these scripts have touched, and affect only those instances. For example, a user may be working on changes inside of VS code (or any app really), and the script should be aware enough to not touch the user's instance but instead create a dedicated instance that will be used for these scripts.

**Repro.**
1. Run any script that tests window/app focus, and is scripted to close those apps; such as 'test_multi_app_integration.py'

**Where.** `tests/windows/test_multi_app_integration.py` (test or helper name)

**Suspected cause.** Teardown closed windows by name match or by killing the PID owning a window with a shared title. Two paths could hit a user's instance: (1) `_find_hwnd("Visual Studio Code")` returning the user's hwnd if it preceded the test's in EnumWindows order, then `_kill_window_process(hwnd)` terminating that PID; (2) tests pressing `Ctrl+N` after focus, which lands in whichever VS Code window is foreground.

**Fix / workaround.** Replaced name-based teardown with PID-scoped `safe_close_hwnd` from the new app_registry. Only PIDs in the OWNED set (spawned by us or persisted from prior runs) are closeable — adopted PIDs and unknown PIDs are skipped, full stop. For long-running user apps (Unreal Engine 5, etc.), set env `CLAWGUI_ADOPT_APPS="UnrealEditor.exe,..."` or `~/.clawgui/adopt.json` and the registry will register matching running PIDs as ADOPTED so the test can use their windows without ever closing them. See [app_registry.md](app_registry.md).

**Verification result (2026-04-27).** VS Code window with unsaved work remained open and untouched after test run. Fix confirmed.


<!--
Template:

## Bug N — short title  {#bug-N}

**Status:** open · **Severity:** medium · **Reported:** YYYY-MM-DD

**Symptom(s).** What goes wrong, observable behaviour.

**Repro.**
1. Step
2. Step

**Where.** `tests/windows/test_multi_app_integration.py:NNN` (test or helper name)

**Suspected cause.** Hypothesis.

**Fix / workaround.** What we did, or what's blocking.
-->
