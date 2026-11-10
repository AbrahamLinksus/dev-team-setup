#!/usr/bin/env python3
"""Spend so far, for result cards and the budget cap (D23).

    python3 cost.py <base> [--since <ISO time>] [--task T-04] [--budget 25] [--json]

<base> is the folder the sessions run in (STATE.md records it). The total comes from Claude
Code's own accounting in its session logs (the same reader bench.py uses), summed over every
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

ROOT = Path(__file__).resolve().parents[3]          # plugin root, which holds bench.py
sys.path.insert(0, str(ROOT))
import bench  # noqa: E402


def task_weights(log_dir: Path, sessions: list[str]) -> dict[str, float]:
    """Price-weighted tokens per task id, from subagent logs whose BRIEF names the task."""
    out: dict[str, float] = defaultdict(float)
    for sid in sessions:
        for path in sorted((log_dir / sid).rglob("*.jsonl")) if (log_dir / sid).is_dir() else []:
            task, replies = None, {}
            for i, d in enumerate(bench.read_lines(path)):
                msg = d.get("message") if isinstance(d.get("message"), dict) else None
                if task is None and d.get("type") == "user" and msg:
                    m = bench.BRIEF_RE.search(bench.text_of(msg))
                    task = m.group(1) if m else ""
                if d.get("type") == "assistant" and msg and msg.get("usage"):
                    replies[msg.get("id") or f"{i}"] = msg["usage"]
            if task:
                out[task] += sum(bench.weighted({f: int(u.get(f) or 0) for f in bench.FIELDS})
                                 for u in replies.values())
    return out


def report(base: Path, since: datetime | None, task: str | None, budget: float | None) -> dict:
    log_dir = bench.log_dir_for(base)
    sessions = bench.sessions_in(log_dir, since) if log_dir.is_dir() else []
    m = bench.measure(log_dir, sessions) if sessions else {"cost_usd": 0.0, "by_agent": {}}
    total = float(m["cost_usd"])
    all_weight = sum(bench.weighted(u) for u in m["by_agent"].values()) or 0.0
    task_cost = None
    if task:
        w = task_weights(log_dir, sessions).get(task, 0.0)
        task_cost = round(total * w / all_weight, 2) if all_weight else 0.0
    over = budget is not None and budget > 0 and total > budget
    parts = []
    if task_cost is not None:
        parts.append(f"≈${task_cost:.2f} this task")
    parts.append(f"${total:.2f} so far")
    if budget:
        parts.append(f"budget ${budget:g} ({100 * total / budget:.0f}%)")
    return {"total_usd": round(total, 2), "task_usd": task_cost, "budget_usd": budget, "over_budget": over,
            "line": "Cost: " + " · ".join(parts)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("base", type=Path)
    ap.add_argument("--since", help="ISO time of the project's start (STATE.md)")
    ap.add_argument("--task")
    ap.add_argument("--budget", type=float)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    # STATE.md writes "2026-11-09 14:20 +05:30"; Python 3.9 needs the offset attached
    since = bench.parse_ts(re.sub(r"\s+([+-]\d\d:?\d\d)$", r"\1", a.since.strip())) if a.since else None
    if a.since and since is None:
        ap.error(f"--since: can't read {a.since!r} as a date and time")
    r = report(a.base, since, a.task, a.budget)
    print(json.dumps(r) if a.json else r["line"])
    sys.exit(3 if r["over_budget"] else 0)


if __name__ == "__main__":
    main()
