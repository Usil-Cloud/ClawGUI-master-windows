<div align="center">
  <img src="assets/ClawGUI-Logo.png" height="120" alt="ClawGUI Logo">
  <h1>ClawGUI — Windows Setup</h1>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-blue" alt="Python">
    <img src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows" alt="Windows">
    <img src="https://img.shields.io/badge/License-Apache%202.0-green" alt="License">
  </p>
</div>

## What This Is

**ClawGUI-Windows** is a natural language remote-control system. A user talks to an agent on their controller device in plain English. That agent drives a second Windows machine — the target — to complete whatever was asked, then returns the results.

The user never touches the target machine. They describe what they want. ClawGUI-Windows figures out how to do it and does it.

### Example interactions

> **"Show me what files are in my Downloads folder."**
> → Agent runs a shell command on the target, reads the output, and tells the user what's there.

> **"How far did I get on my farmhouse model in Blender?"**
> → Agent opens Blender on the target, focuses the window, takes a screenshot, and returns it — along with a summary and a prompt: *"Here's where you left off. Want to keep going?"*

> **"Yeah, let's keep working. Rotate the roof section 15 degrees and show me how it looks."**
> → Agent drives Blender on the target through GUI actions (clicks, keyboard shortcuts, viewport navigation), screenshots the result, and returns it.

### What "driving" means in practice

ClawGUI-Windows uses two execution modes depending on what the task requires:

| Mode | Examples |
|------|---------|
| **GUI simulation** | Click, scroll, type, drag, hotkeys — for visual apps (Blender, browsers, IDEs, Explorer) |
| **System commands** | Shell/CLI execution with stdout returned — for file operations, installs, scripts, queries |

A co-working session may mix both in a single goal. The agent decides which to use.

---

## Technical Overview

This repo contains the Windows-ready build of **ClawGUI-master**. The primary entry point on the target machine is the **Windows Agent Server (WAS)**, which exposes a REST + MCP interface. The controller (where the user talks to the agent) sends tasks to WAS, which executes them and returns results — screenshots, command output, file contents — back to the agent.

---

## Prerequisites

On a **brand-new Windows machine**, open PowerShell as Administrator and run:

```powershell
winget install Python.Python.3.12 Git.Git
```

Close and reopen your terminal after this so `python` and `git` are on PATH. If your machine already has Python 3.11+ and Git, skip this step.

---

## Setup (4 commands)

```powershell
git clone https://github.com/Usil-Cloud/ClawGUI-master-windows.git
cd ClawGUI-master-windows\clawgui-agent
pip install -r requirements_windows.txt && pip install -e . && pip install -e nanobot/
python windows_agent_server.py
```

The server starts on **port 7860** by default.

| Endpoint | URL |
|---|---|
| Web UI / Status | http://localhost:7860 |
| REST API | http://localhost:7860/api/ |
| MCP endpoint | http://localhost:7860/mcp |
| Interactive docs | http://localhost:7860/docs |

---

## Configuration (only needed for standalone mode)

**Smoketest / server-only**: if this machine is acting purely as the Windows Agent Server — receiving tasks from a controller on another machine — you do **not** need an API key here. The controller handles VLM calls.

**Standalone mode**: if you want this machine to also drive the VLM reasoning loop itself, set an API key for whichever provider you're using (OpenRouter, Zhipu AI, a local vLLM server, etc.). These providers all use the OpenAI-compatible API format:

```powershell
# Example: OpenRouter
$env:OPENAI_API_KEY = "sk-or-..."

# Example: local vLLM (no key required — just set the base URL in config)
```

Or add it to a `.env` file inside `clawgui-agent/`:

```
OPENAI_API_KEY=your-provider-key-here
```

See [`clawgui-agent/README.md`](clawgui-agent/README.md) for the full provider/model config reference.

---

## Custom Host / Port

```powershell
python windows_agent_server.py --host 0.0.0.0 --port 8080
```

---

## Pointing a Controller at This Machine

On the controller machine, point the agent server address to:

```
http://<this-machine-ip>:7860
```

Then send tasks from the controller's Web UI (`python webui.py`) or CLI (`python main.py`).

---

## Smoke Test Checklist

- [ ] Server starts without errors
- [ ] `http://localhost:7860/docs` loads in browser
- [ ] `/api/` returns a JSON response
- [ ] Controller can reach `http://<ip>:7860` from the network
- [ ] A test task completes end-to-end (screenshot → action loop)

---

## Full Documentation

See [`clawgui-agent/README.md`](clawgui-agent/README.md) for the complete guide: model configuration, chat platform integrations (Feishu, Telegram, Slack, QQ, and more), memory system, and evaluation pipeline.

---

## License

[Apache License 2.0](LICENSE)
