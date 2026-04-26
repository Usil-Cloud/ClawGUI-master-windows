---
name: Window Manager overview
description: What Feature 1-D does and its public API.
type: project
last_updated: 2026-04-25
status: active
---

# Window Manager — Overview

## Phase role
Feature 1-D in the Phase 1 local-execution layer. The agent calls `focus_window(title)` before any keyboard/mouse action so input goes to the correct app.

## Public API

```python
from phone_agent.windows import window_manager as wm

wm.list_windows() -> list[WindowInfo]
wm.focus_window(title: str, device_id: str | None = None) -> bool
wm.minimize_window(title: str, device_id: str | None = None) -> bool
wm.maximize_window(title: str, device_id: str | None = None) -> bool
wm.close_window(title: str, device_id: str | None = None) -> bool
```

`WindowInfo` dataclass:

```python
@dataclass
class WindowInfo:
    hwnd: int
    title: str
    visible: bool
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)  # (left, top, right, bottom)
```

## Title matching

All `*_window(title=...)` calls use **case-insensitive partial match** on `GetWindowText`. So `focus_window("note")` matches `"Untitled - Notepad"`. The first match in `EnumWindows` order wins.

## Local vs remote

When `device_id` is `None` or `"local"`, calls hit `_local_*` helpers via `pywin32`. Otherwise, the call is forwarded to the Windows Agent Server (Phase 3) over HTTP.

| Operation | Remote endpoint |
|-----------|-----------------|
| `list_windows` | `POST /api/windows/list` |
| `focus_window` | `POST /api/action/focus_window` |
| `minimize_window` | `POST /api/windows/minimize` |
| `maximize_window` | `POST /api/windows/maximize` |
| `close_window` | `POST /api/windows/close` |

## Filtering rules in `list_windows`
- `IsWindowVisible(hwnd)` must be true.
- `GetWindowText(hwnd)` must be non-empty.
- Order is whatever `EnumWindows` yields.
- On any exception → returns `[]` (does not raise).

See [design.md](design.md) for the focus-window strategy and edge cases.
