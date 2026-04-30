---
name: ClawGUI Docs Conventions
description: Rules for the docs/ tree — mirroring, templates, headers, indexing, maintenance.
type: reference
---

# Docs Conventions (ClawGUI pilot)

This `docs/` tree is the pilot for a project-wide convention. Once proven here, it becomes the standard for all Projects.

## 1. Mirroring rule

Every doc lives at `docs/<source-path>.md`.

- Source: `phone_agent/windows/window_manager.py`
- Doc: `docs/phone_agent/windows/window_manager.md`
- Source: `tests/windows/test_screenshot.py`
- Doc: `docs/tests/windows/test_screenshot.md`

Predictable, no hunting. If the source moves, the doc moves with it.

## 2. Companion `.md` template (Medium)

```markdown
---
mirrors: <source path relative to clawgui-agent/>
last_updated: YYYY-MM-DD
status: active            # active | stable | broken | deprecated
---

# <file name without extension>

## Purpose
1–3 sentences. Why this file exists.

## Approach
High-level — key decisions, dataclasses, important branching. Not line-by-line.

## Status
What works, what's pending, what's known-broken.

## Known Bugs
- [ ] Short description — see `docs/features/<feature>/bugs.md#bug-N`

## Linked Docs
- Parent: `docs/features/<feature>/_index.md`
- Related: `docs/<other source>.md`
```

## 3. Code header convention

Every touched code file gets a 2-line header at the very top (after module docstring is fine):

```python
# Notes: docs/tests/windows/test_screenshot.md
# Bug tracker: docs/features/auto_focus_screenshot/bugs.md
```

The `Bug tracker:` line is added only when at least one bug exists. Remove it once the tracker is empty.

## 4. Big features get a hub

When a feature spans multiple source files or has nontrivial design notes, build a hub:

```
docs/features/<feature_name>/
├── _index.md      # parent doc — links to children + status table
├── overview.md    # what + why
├── design.md      # key decisions + dataclasses + flow
├── bugs.md        # bug tracker, anchors per bug
└── ... more children as needed
```

Parent (`_index.md`) **explicitly** links each child. The folder's auto-style listing is a safety net, not the canonical path.

## 5. `_index.md` per folder

Each non-trivial folder under `docs/` has an `_index.md` listing every doc in that folder:

```markdown
- [test_screenshot](test_screenshot.md) — Feature 1-A unit + integration tests · status: active
- [test_window_manager](test_window_manager.md) — Feature 1-D unit + integration tests · status: active
```

## 6. Maintenance trigger

Update the doc when **any** of these happen:
- New feature or new file added
- Bug found, fixed, or status changed
- Approach changed (different dataclass, different branching, swapped library)
- Status flipped (active → broken, broken → stable, etc.)

**Do not** update for: typo fixes, formatting, single-line tweaks, comment changes.

When updating, bump `last_updated` in frontmatter and say "doc updated" in the chat reply.

## 7. PROJECT_MAP.md

Top-level `clawgui-agent/PROJECT_MAP.md` is a feature-level index. Useful for navigating without grep. Source-of-truth for "what features exist and where do their docs live."
