"""Windows application name → executable path mapping."""

APP_PACKAGES_WINDOWS: dict[str, str] = {
    # System
    "Notepad": "notepad.exe",
    "notepad": "notepad.exe",
    "Calculator": "calc.exe",
    "calculator": "calc.exe",
    "Paint": "mspaint.exe",
    "File Explorer": "explorer.exe",
    "Task Manager": "taskmgr.exe",
    "Settings": "ms-settings:",
    # Browsers
    "Chrome": "chrome.exe",
    "Google Chrome": "chrome.exe",
    "Firefox": "firefox.exe",
    "Edge": "msedge.exe",
    "Microsoft Edge": "msedge.exe",
    # Development
    "Visual Studio Code": "code",
    "VS Code": "code",
    "code": "code",
    "Cursor": "cursor",
    "Terminal": "wt.exe",
    "Windows Terminal": "wt.exe",
    "PowerShell": "powershell.exe",
    "Command Prompt": "cmd.exe",
    # Creative / Game Dev
    "Blender": "blender.exe",
    "Unreal Engine": "UnrealEditor.exe",
    # Productivity
    "Slack": "slack.exe",
    "Discord": "discord.exe",
    "Zoom": "Zoom.exe",
    "Spotify": "Spotify.exe",
}
