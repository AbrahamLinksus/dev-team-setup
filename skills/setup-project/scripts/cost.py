#!/usr/bin/env python3
"""Spend so far, for result cards and the budget cap.

    python3 cost.py <base> [--since <ISO time>] [--task T-04] [--budget 25] [--json]
    python3 cost.py <base> --since … --task T-04 --result      cost by role, for TASKS.md's Result line
    python3 cost.py <base> --since … --rework T-01 T-02 …      tasks over 2x the milestone median

<base> is the folder the sessions run in (STATE.md records it). The total comes from Claude
Code's own accounting in its session logs (read by usage.py), summed over every
session in <base> since --since (the project's start). A task's share is estimated: the
task's own agents' price-weighted tokens (agents whose BRIEF names the task) as a fraction of
the run's, times the total. Prints one card line, e.g.

    Cost: ≈$0.42 this task · $3.10 so far · budget $25 (12%)

and exits 3 when the total is over --budget, so the Orchestrator can stop and ask.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage  # noqa: E402


def task_breakdown(log_dir: Path, sessions: list[str]) -> dict[str, dict[str, dict]]:
    """Per task id, per agent role: price-weighted tokens and how many times the role was
    spawned, from subagent logs whose BRIEF names the task."""
    out: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"weight": 0.0, "spawns": 0}))
    for sid in sessions:
        for path in sorted((log_dir / sid).rglob("*.jsonl")) if (log_dir / sid).is_dir() else []:
            task, agent, replies = None, "", {}
            for i, d in enumerate(usage.read_lines(path)):
                msg = d.get("message") if isinstance(d.get("message"), dict) else None
                if task is None and d.get("type") == "user" and msg:
                    m = usage.BRIEF_RE.search(usage.text_of(msg))
                    task, agent = (m.group(1), m.group(2)) if m else ("", "")
                if d.get("type") == "assistant" and msg and msg.get("usage"):
                    replies[msg.get("id") or f"{i}"] = msg["usage"]
            if task:
                row = out[task][agent]
                row["weight"] += sum(usage.weighted({f: int(u.get(f) or 0) for f in usage.FIELDS})
                                     for u in replies.values())
                row["spawns"] += 1
    return out


def task_weights(log_dir: Path, sessions: list[str]) -> dict[str, float]:
    """Price-weighted tokens per task id."""
    return {t: sum(r["weight"] for r in roles.values()) for t, roles in task_breakdown(log_dir, sessions).items()}


def role_line(task_usd: float, roles: dict[str, dict]) -> str:
    """The TASKS.md Result line's cost part: ≈$0.42 · backend-coder 55% · tester 30% · reviewer 15%."""
    total = sum(r["weight"] for r in roles.values())
    if not total:
        return f"≈${task_usd:.2f}"
    parts = sorted(((100 * r["weight"] / total, name) for name, r in roles.items()), reverse=True)
    return f"≈${task_usd:.2f} · " + " · ".join(f"{name} {pct:.0f}%" for pct, name in parts if pct >= 0.5)


def rework(costs: dict[str, float], breakdown: dict[str, dict[str, dict]], ids: list[str]) -> list[str]:
    """Tasks over 2x the median cost of `ids`, with their debugger rounds, for the milestone card."""
    import statistics
    mine = {t: costs.get(t, 0.0) for t in ids}
    if len(mine) < 2:
        return []
    med = statistics.median(mine.values())
    out = []
    for t, c in sorted(mine.items(), key=lambda x: -x[1]):
        if med and c > 2 * med:
            rounds = breakdown.get(t, {}).get("debugger", {}).get("spawns", 0)
            out.append(f"{t} ${c:.2f} ({c / med:.1f}x the median ${med:.2f}) · "
                       f"{rounds} debugger round{'' if rounds == 1 else 's'}")
    return out


def report(base: Path, since: datetime | None, task: str | None, budget: float | None,
           milestone: list[str] | None = None) -> dict:
    log_dir = usage.log_dir_for(base)
    sessions = usage.sessions_in(log_dir, since) if log_dir.is_dir() else []
    m = usage.measure(log_dir, sessions) if sessions else {"cost_usd": 0.0, "by_agent": {}}
    total = float(m["cost_usd"])
    all_weight = sum(usage.weighted(u) for u in m["by_agent"].values()) or 0.0
    task_cost = None
    breakdown = task_breakdown(log_dir, sessions) if (task or milestone) else {}

    def usd(t: str) -> float:
        w = sum(r["weight"] for r in breakdown.get(t, {}).values())
        return round(total * w / all_weight, 2) if all_weight else 0.0

    roles = None
    if task:
        task_cost = usd(task)
        roles = {name: round(total * r["weight"] / all_weight, 2) if all_weight else 0.0
                 for name, r in breakdown.get(task, {}).items()}
    over = budget is not None and budget > 0 and total > budget
    parts = []
    if task_cost is not None:
        parts.append(f"≈${task_cost:.2f} this task")
    parts.append(f"${total:.2f} so far")
    if budget:
        parts.append(f"budget ${budget:g} ({100 * total / budget:.0f}%)")
    out = {"total_usd": round(total, 2), "task_usd": task_cost, "budget_usd": budget, "over_budget": over,
           "line": "Cost: " + " · ".join(parts)}
    if task:
        out["roles_usd"] = roles
        out["result_cost"] = role_line(task_cost or 0.0, breakdown.get(task, {}))
    if milestone:
        out["rework"] = rework({t: usd(t) for t in milestone}, breakdown, milestone)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("base", type=Path)
    ap.add_argument("--since", help="ISO time of the project's start (STATE.md)")
    ap.add_argument("--task")
    ap.add_argument("--budget", type=float)
    ap.add_argument("--result", action="store_true",
                    help="with --task: print the TASKS.md Result line's cost by role instead")
    ap.add_argument("--rework", nargs="+", metavar="ID",
                    help="the milestone's task IDs: print tasks over 2x their median cost, with debugger rounds")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.result and not a.task:
        ap.error("--result needs --task")
    # STATE.md writes "2026-11-09 14:20 +05:30"; Python 3.9 needs the offset attached
    since = usage.parse_ts(re.sub(r"\s+([+-]\d\d:?\d\d)$", r"\1", a.since.strip())) if a.since else None
    if a.since and since is None:
        ap.error(f"--since: can't read {a.since!r} as a date and time")
    r = report(a.base, since, a.task, a.budget, a.rework)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    elif a.result:
        print(r["result_cost"])
    elif a.rework:
        print("\n".join(["Rework: " + x for x in r["rework"]]) or "Rework: no task over 2x the milestone's median cost")
    else:
        print(r["line"])
    sys.exit(3 if r["over_budget"] else 0)


if __name__ == "__main__":
    main()
