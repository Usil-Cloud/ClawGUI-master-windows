"""Windows application name to executable mapping.

IMPORTANT -- PATH-only entries only.
--------------------------------------
This dict is Tier 1 of AppResolver: it should contain ONLY apps whose
executable is genuinely on the system PATH on a standard Windows install.
Do NOT add user-installed apps (Discord, Slack, Zoom, Spotify, Blender, etc.)
here -- AppResolver Tier 2 (Registry) and Tier 4 (dynamic scan) find those
automatically without hardcoding version-dependent paths.

Rule of thumb: if you need a full path like
  C:\\Users\\...\\AppData\\Local\\Discord\\app-1.0.9171\\Discord.exe
it does NOT belong here.
"""

APP_PACKAGES_WINDOWS: dict[str, str] = {
    # ---- Windows built-ins (always in PATH) ----
    "Notepad":        "notepad.exe",
    "notepad":        "notepad.exe",
    "Calculator":     "calc.exe",
    "calculator":     "calc.exe",
    "Paint":          "mspaint.exe",
    "paint":          "mspaint.exe",
    "File Explorer":  "explorer.exe",
    "Explorer":       "explorer.exe",
    "Task Manager":   "taskmgr.exe",
    "Settings":       "ms-settings:",

    # ---- Dev tools that self-add to PATH ----
    "Visual Studio Code": "code",
    "VS Code":            "code",
    "code":               "code",
    "Cursor":             "cursor",
    "Terminal":           "wt.exe",
    "Windows Terminal":   "wt.exe",
    "PowerShell":         "powershell.exe",
    "powershell":         "powershell.exe",
    "Command Prompt":     "cmd.exe",
    "cmd":                "cmd.exe",

    # ---- Browsers that self-add to PATH ----
    # (Chrome/Edge/Firefox also register in App Paths, but listing here
    #  avoids a registry round-trip for the most common cases)
    "Edge":          "msedge.exe",
    "Microsoft Edge": "msedge.exe",
}
