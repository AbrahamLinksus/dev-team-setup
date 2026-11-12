#!/usr/bin/env python3
"""Task graph for /setup-project: reads TASKS.md and says what can run at the same time.

    taskgraph.py TASKS.md                     waves, critical path, parallel factor, warnings
    taskgraph.py TASKS.md --json              the same as JSON (the build loop schedules from it)
    taskgraph.py TASKS.md --summary           plain words for the planning card
    taskgraph.py TASKS.md --mermaid           a flowchart (critical path highlighted) for capture.py
    taskgraph.py TASKS.md --ready [--json]    tasks to start now, from the earliest unfinished milestone:
                                              dependencies Done, no shared files with running tasks,
                                              up to --max running at once; --avoid M2 also skips tasks
                                              sharing files with milestone M2 (its card is waiting)
    taskgraph.py TASKS.md --undeclared T-04   changed paths on stdin → the ones T-04's Files don't cover

A wave is one dependency level, split so that no two tasks in it share a file and no wave holds
more than --max tasks (default 3). Every task needs Owner, Depends on and Files.
Exit codes: 0 ok · 1 usage · 2 TASKS.md is invalid (missing fields, unknown IDs, a cycle).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

TASK_RE = re.compile(r"^#{2,4}\s+(T-\d+[A-Za-z0-9]*)\s*(?:[·:—-]\s*)?(.*?)\s*$")
MILESTONE_RE = re.compile(r"^##\s+(M\d+)\b\s*(?:[·:—-]\s*)?(.*?)\s*$")
FIELD_RE = re.compile(r"^\s*-\s*(Owner|Depends on|Files|Status):\s*(.*?)\s*$", re.I)
ID_RE = re.compile(r"T-\d+[A-Za-z0-9]*")
REQUIRED = ("owner", "depends on", "files")
RUNNING = {"in progress", "review", "needs you", "needs you (batch)"}


class Invalid(Exception):
    pass


def parse(text: str) -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    cur = None
    milestone = ""
    for line in text.splitlines():
        m = MILESTONE_RE.match(line)
        if m and not TASK_RE.match(line):
            milestone, cur = m.group(1), None
            continue
        m = TASK_RE.match(line)
        if m:
            if m.group(1) in tasks:
                raise Invalid(f"{m.group(1)} appears twice")
            cur = tasks[m.group(1)] = {"id": m.group(1), "title": m.group(2), "milestone": milestone, "fields": {}}
            continue
        if line.startswith("#"):
            cur = None
            continue
        m = FIELD_RE.match(line)
        if cur is not None and m:
            cur["fields"][m.group(1).lower()] = m.group(2).replace("`", "")
    missing = [f"{t} ({', '.join(f.title() for f in REQUIRED if not d['fields'].get(f))})"
               for t, d in tasks.items() if any(not d["fields"].get(f) for f in REQUIRED)]
    if missing:
        raise Invalid("tasks missing Owner, Depends on or Files: " + "; ".join(missing))
    for d in tasks.values():
        f = d.pop("fields")
        d["owner"] = [o.strip() for o in f["owner"].split(",") if o.strip()]
        d["depends"] = ID_RE.findall(f["depends on"])
        d["files"] = [p[2:] if p.startswith("./") else p for p in (q.strip() for q in f["files"].split(",")) if p]
        d["status"] = (f.get("status") or "Backlog").split("·")[0].strip()
    unknown = sorted({f"{t} → {dep}" for t, d in tasks.items() for dep in d["depends"] if dep not in tasks})
    if unknown:
        raise Invalid("unknown task IDs in Depends on: " + ", ".join(unknown))
    if not tasks:
        raise Invalid("no tasks found (headings like '### T-01 · title')")
    return tasks


def overlaps(a: str, b: str) -> bool:
    """Two Files entries (paths or globs) may touch the same file."""
    a, b = a.rstrip("/"), b.rstrip("/")
    return (a == b or fnmatch(a, b) or fnmatch(b, a)
            or b.startswith(a + "/") or a.startswith(b + "/"))


def share_files(x: dict, y: dict) -> bool:
    return any(overlaps(a, b) for a in x["files"] for b in y["files"])


def levels(tasks: dict[str, dict]) -> dict[str, int]:
    level: dict[str, int] = {}
    state: dict[str, int] = {}   # 1 visiting, 2 done

    def visit(t: str, path: list[str]) -> int:
        if state.get(t) == 2:
            return level[t]
        if state.get(t) == 1:
            raise Invalid("dependency cycle: " + " → ".join(path[path.index(t):] + [t]))
        state[t] = 1
        level[t] = 1 + max((visit(d, path + [t]) for d in tasks[t]["depends"]), default=0)
        state[t] = 2
        return level[t]

    for t in sorted(tasks):
        visit(t, [])
    return level


def chains(tasks: dict[str, dict]) -> dict[str, int]:
    """Longest chain of tasks from each task to the end of the plan (itself included)."""
    succ: dict[str, list[str]] = {t: [] for t in tasks}
    for t, d in tasks.items():
        for dep in d["depends"]:
            succ[dep].append(t)
    memo: dict[str, int] = {}

    def length(t: str) -> int:
        if t not in memo:
            memo[t] = 1 + max((length(s) for s in succ[t]), default=0)
        return memo[t]

    for t in tasks:
        length(t)
    return memo


def build(tasks: dict[str, dict], cap: int) -> dict:
    level, chain = levels(tasks), chains(tasks)
    for t, d in tasks.items():
        d["level"], d["chain"] = level[t], chain[t]
    order = sorted(tasks, key=lambda t: (level[t], -chain[t], t))
    waves: list[list[str]] = []
    for lv in sorted(set(level.values())):
        mine: list[list[str]] = []
        for t in (x for x in order if level[x] == lv):
            for w in mine:
                if len(w) < cap and not any(share_files(tasks[t], tasks[o]) for o in w):
                    w.append(t)
                    break
            else:
                mine.append([t])
        waves.extend(mine)
    path = [sorted(tasks, key=lambda t: (-chain[t], level[t], t))[0]]
    while True:
        nxt = [t for t in tasks if path[-1] in tasks[t]["depends"]]
        if not nxt:
            break
        path.append(sorted(nxt, key=lambda t: (-chain[t], t))[0])
    factor = round(len(tasks) / len(waves), 2)
    warnings = []
    if len(tasks) >= 4 and factor < 1.5:
        warnings.append(f"parallel factor {factor} is under 1.5: say why on the planning card, or move shared "
                        f"helpers into the foundation task so feature tasks stop sharing files")
    return {"tasks": [tasks[t] for t in sorted(tasks, key=lambda t: (level[t], t))], "waves": waves,
            "critical_path": path, "parallel_factor": factor, "warnings": warnings}


def ready(tasks: dict[str, dict], cap: int, avoid: str = "") -> list[str]:
    """Tasks to start now, from the earliest milestone that isn't finished. `avoid` names a
    milestone under review: skip tasks sharing a file with any of its tasks (its card may still
    ask for changes there)."""
    done = {t for t, d in tasks.items() if d["status"].lower() == "done"}
    running = [t for t, d in tasks.items() if d["status"].lower() in RUNNING]
    order = []
    for d in tasks.values():
        if d["milestone"] not in order:
            order.append(d["milestone"])
    open_ms = [m for m in order if any(d["milestone"] == m and d["id"] not in done for d in tasks.values())]
    current = open_ms[0] if open_ms else None
    held = [d for d in tasks.values() if avoid and d["milestone"] == avoid]
    picked: list[str] = []
    slots = max(0, cap - len(running))
    candidates = sorted((t for t, d in tasks.items() if d["status"].lower() == "backlog"
                         and d["milestone"] == current and set(d["depends"]) <= done),
                        key=lambda t: (-tasks[t]["chain"], t))
    for t in candidates:
        if len(picked) >= slots:
            break
        if any(share_files(tasks[t], tasks[o]) for o in running + picked) or any(share_files(tasks[t], h) for h in held):
            continue
        picked.append(t)
    return picked


def undeclared(task: dict, changed: list[str]) -> list[str]:
    return [p for p in changed if not any(overlaps(p, f) for f in task["files"])]


def mermaid(graph: dict) -> str:
    crit = set(graph["critical_path"])
    node = {d["id"]: re.sub(r"\W", "_", d["id"]) for d in graph["tasks"]}
    lines = ["flowchart LR"]
    by_id = {d["id"]: d for d in graph["tasks"]}
    for n, wave in enumerate(graph["waves"], 1):
        lines.append(f'  subgraph R{n}["Round {n}"]')
        for t in wave:
            title = by_id[t]["title"].replace('"', "'")
            lines.append(f'    {node[t]}["{t} · {title}"]')
        lines.append("  end")
    for d in graph["tasks"]:
        for dep in d["depends"]:
            arrow = "==>" if dep in crit and d["id"] in crit else "-->"
            lines.append(f"  {node[dep]} {arrow} {node[d['id']]}")
    lines.append("  classDef critical fill:#fde68a,stroke:#b45309,stroke-width:2px")
    lines.append("  class " + ",".join(node[t] for t in graph["critical_path"]) + " critical")
    return "\n".join(lines)


def summary(graph: dict) -> str:
    out = []
    for n, wave in enumerate(graph["waves"], 1):
        if len(wave) == 1:
            what = "1 task on its own"
        else:
            what = f"{len(wave)} features at the same time"
        out.append(f"Round {n}: {what} ({', '.join(wave)})")
    out.append(f"Longest chain: {' → '.join(graph['critical_path'])} "
               f"({len(graph['critical_path'])} of {len(graph['waves'])} rounds)")
    out.append(f"Parallel factor: {graph['parallel_factor']} "
               f"({len(graph['tasks'])} tasks in {len(graph['waves'])} rounds)")
    out.extend(f"Warning: {w}" for w in graph["warnings"])
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("tasks_md")
    ap.add_argument("--max", type=int, default=3, help="tasks per wave / running at once (default 3)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--mermaid", action="store_true")
    mode.add_argument("--ready", action="store_true")
    mode.add_argument("--undeclared", metavar="ID")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--avoid", metavar="M<n>", help="with --ready: skip tasks sharing files with this milestone")
    a = ap.parse_args(argv)
    if a.max < 1:
        ap.error("--max must be at least 1")
    try:
        tasks = parse(Path(a.tasks_md).read_text(encoding="utf-8"))
        graph = build(tasks, a.max)
    except OSError as e:
        print(f"taskgraph: {e}", file=sys.stderr)
        return 1
    except Invalid as e:
        print(f"taskgraph: {a.tasks_md}: {e}", file=sys.stderr)
        return 2
    if a.undeclared:
        if a.undeclared not in tasks:
            print(f"taskgraph: no task {a.undeclared}", file=sys.stderr)
            return 1
        extra = undeclared(tasks[a.undeclared], [ln.strip() for ln in sys.stdin if ln.strip()])
        print(json.dumps(extra) if a.json else "\n".join(extra))
        return 0
    if a.ready:
        picked = ready(tasks, a.max, a.avoid or "")
        print(json.dumps([tasks[t] for t in picked], ensure_ascii=False) if a.json else "\n".join(picked))
        return 0
    if a.json:
        print(json.dumps(graph, ensure_ascii=False, indent=1))
    elif a.mermaid:
        print(mermaid(graph))
    else:
        print(summary(graph))
    return 0


if __name__ == "__main__":
    sys.exit(main())
