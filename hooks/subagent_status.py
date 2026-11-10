#!/usr/bin/env python3
"""Subagent status line for the dev team (D22).

Claude Code runs this on every refresh tick with every visible subagent row as JSON on stdin
(see `subagentStatusLine` in the Claude Code status line docs). For this plugin's agents only,
it prints one override per row:

    ⏳ backend-coder · T-04 · implement · 3m12s · 41k tok · 18% ctx

so the owner sees who is working on what without reading the chat. Rows from other plugins or
built-in agents are left alone (no line printed = default rendering). It never fails loudly:
bad input prints nothing.
"""
from __future__ import annotations

import json
import sys
import time

PLUGIN = "dev-team-setup"
ICON = {"running": "⏳", "completed": "✅", "failed": "❌", "killed": "⏹"}


def tokens(n: float) -> str:
    return f"{n / 1000:.0f}k" if n >= 1000 else f"{n:.0f}"


def elapsed(start_ms: float, now: float) -> str:
    s = max(0, int(now - start_ms / 1000))
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def row(task: dict, now: float, width: int) -> str | None:
    agent_type = str(task.get("agentType") or "")
    if not agent_type.startswith(PLUGIN + ":"):
        return None
    parts = [f"{ICON.get(task.get('status'), '·')} {agent_type.split(':')[-1]}"]
    # The Orchestrator spawns every agent with description "<task id> · <step>" (SKILL.md, step protocol)
    what = str(task.get("description") or "").strip()
    if what:
        parts.append(what)
    if task.get("startTime"):
        parts.append(elapsed(float(task["startTime"]), now))
    count = task.get("tokenCount")
    if isinstance(count, (int, float)):
        parts.append(f"{tokens(count)} tok")
        window = task.get("contextWindowSize")
        if isinstance(window, (int, float)) and window:
            parts.append(f"{100 * count / window:.0f}% ctx")
    text = " · ".join(parts)
    return text if len(text) <= width else text[: max(1, width - 1)] + "…"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    width = int(data.get("columns") or 80)
    now = time.time()
    for task in data.get("tasks") or []:
        if not isinstance(task, dict) or "id" not in task:
            continue
        content = row(task, now, width)
        if content is not None:
            print(json.dumps({"id": task["id"], "content": content}, ensure_ascii=False))


if __name__ == "__main__":
    main()
