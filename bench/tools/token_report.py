#!/usr/bin/env python3
"""Token report for Claude Code sessions, including every subagent.

Reads the session logs Claude Code writes to ~/.claude/projects/<project>/:
  <session-id>.jsonl                 main session (older versions also put subagent
                                     lines here, marked "isSidechain": true)
  <session-id>/**/*.jsonl            subagent logs (newer versions)

Totals come from Claude Code's own accounting: the last "cost-state" line of each
session (the same numbers /cost shows, including background calls such as summaries
and titles that never appear as replies). The per-agent split comes from the logged
replies (each counted once); the difference is shown as "background calls".
Older logs without cost-state fall back to replies only and are marked as a lower bound.

Usage (run from the folder you started `claude` in, or pass --project-dir):
  python3 bench/tools/token_report.py --latest               # newest session
  python3 bench/tools/token_report.py --session <id> [...]   # specific sessions
  python3 bench/tools/token_report.py --since 2026-11-09T10:00   # every session started after this
  add --label "plugin run" for the summary row, --json for machine-readable output
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
BRIEF_RE = re.compile(r"BRIEF\s*·\s*(\S+)\s*·\s*([a-z][a-z0-9-]+)")


def project_dir_for(cwd: Path) -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def text_of(message: dict) -> str:
    c = message.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict))
    return ""


def read_lines(path: Path):
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def agent_label(path: Path) -> str:
    """Name a subagent log: dev-team BRIEF header, else an agent-type field, else 'subagent'."""
    meta = path.with_suffix(".meta.json")
    if meta.exists():
        try:
            m = json.loads(meta.read_text())
            for k in ("agentType", "subagent_type", "agent_type"):
                if m.get(k):
                    return str(m[k]).split(":")[-1]
        except ValueError:
            pass
    for d in read_lines(path):
        for k in ("agentType", "subagent_type", "agent_type"):
            if d.get(k):
                return str(d[k]).split(":")[-1]
        if d.get("type") == "user" and isinstance(d.get("message"), dict):
            m = BRIEF_RE.search(text_of(d["message"]))
            return m.group(2) if m else "subagent"
    return "subagent"


class Totals:
    def __init__(self):
        self.by_agent = defaultdict(lambda: defaultdict(int))
        self.by_model = defaultdict(lambda: defaultdict(int))
        self.calls = defaultdict(int)
        self.first = self.last = None
        self.sessions = []

    def add(self, agent: str, model: str, usage: dict, ts: datetime | None):
        for f in FIELDS:
            v = int(usage.get(f) or 0)
            self.by_agent[agent][f] += v
            self.by_model[model][f] += v
        self.calls[agent] += 1
        if ts:
            self.first = ts if self.first is None or ts < self.first else self.first
            self.last = ts if self.last is None or ts > self.last else self.last


def collect(files: list[tuple[Path, str | None]], totals: Totals) -> None:
    """files: (path, fixed agent label or None for the main session file)."""
    for path, fixed in files:
        replies: dict[str, tuple[str, str, dict, datetime | None]] = {}
        for i, d in enumerate(read_lines(path)):
            if d.get("type") != "assistant" or not isinstance(d.get("message"), dict):
                continue
            msg = d["message"]
            usage = msg.get("usage")
            if not usage:
                continue
            key = msg.get("id") or d.get("requestId") or f"{path}:{i}"
            agent = fixed or ("subagent (sidechain)" if d.get("isSidechain") else "main session")
            prev = replies.get(key)
            # keep the most complete copy of each reply (largest output count)
            if prev is None or int(usage.get("output_tokens") or 0) >= int(prev[2].get("output_tokens") or 0):
                replies[key] = (agent, msg.get("model", "unknown"), usage, parse_ts(d.get("timestamp")))
        for agent, model, usage, ts in replies.values():
            totals.add(agent, model, usage, ts)


CAMEL = {"inputTokens": "input_tokens", "cacheCreationInputTokens": "cache_creation_input_tokens",
         "cacheReadInputTokens": "cache_read_input_tokens", "outputTokens": "output_tokens"}
BACKGROUND = "background calls (not logged as replies)"


def read_cost_state(main: Path) -> dict | None:
    """Last cost-state line of a session: Claude Code's cumulative totals (what /cost shows)."""
    last = None
    for d in read_lines(main):
        if d.get("type") == "cost-state" and isinstance(d.get("modelUsage"), dict):
            last = d
    if last is None:
        return None
    by_model = {m: {f: int(u.get(c) or 0) for c, f in CAMEL.items()} for m, u in last["modelUsage"].items()}
    return {"cost": float(last.get("totalCostUSD") or 0), "by_model": by_model,
            "minutes": (last.get("totalDuration") or 0) / 60000, "unknown_cost": bool(last.get("hasUnknownModelCost"))}


def sum_fields(d: dict) -> dict:
    out = defaultdict(int)
    for u in d.values():
        for f in FIELDS:
            out[f] += u[f]
    return out


def session_files(pdir: Path, sid: str) -> list[tuple[Path, str | None]]:
    files: list[tuple[Path, str | None]] = []
    main = pdir / f"{sid}.jsonl"
    if main.exists():
        files.append((main, None))
    sub = pdir / sid
    if sub.is_dir():
        files += [(p, agent_label(p)) for p in sorted(sub.rglob("*.jsonl"))]
    return files


def first_ts(path: Path) -> datetime | None:
    for d in read_lines(path):
        ts = parse_ts(d.get("timestamp"))
        if ts:
            return ts
    return None


def fmt(n: int) -> str:
    return f"{n:,}"


def row(name: str, u: dict, calls: int | None = None) -> str:
    ctx = u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
    cells = [name, fmt(u["input_tokens"]), fmt(u["cache_creation_input_tokens"]),
             fmt(u["cache_read_input_tokens"]), fmt(u["output_tokens"]), fmt(ctx + u["output_tokens"])]
    if calls is not None:
        cells.insert(1, str(calls))
    return "| " + " | ".join(cells) + " |"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-dir", type=Path, help="~/.claude/projects/<project> (default: from current folder)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--latest", action="store_true")
    g.add_argument("--session", nargs="+")
    g.add_argument("--since", help="ISO time; includes every session that started at or after it")
    ap.add_argument("--label", default="run")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    pdir = a.project_dir or project_dir_for(Path.cwd())
    if not pdir.is_dir():
        print(f"No session logs at {pdir}. Pass --project-dir ~/.claude/projects/<name> "
              f"(ls ~/.claude/projects to find it).", file=sys.stderr)
        return 1
    mains = sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if a.latest:
        sids = [mains[-1].stem] if mains else []
    elif a.session:
        sids = a.session
    else:
        since = parse_ts(a.since)
        if since is None:
            print("--since must be an ISO time like 2026-11-09T10:00", file=sys.stderr)
            return 1
        if since.tzinfo is None:
            since = since.astimezone()  # local time
        sids = [p.stem for p in mains if (t := first_ts(p)) and t >= since]
    if not sids:
        print("No matching sessions.", file=sys.stderr)
        return 1

    totals = Totals()                                   # visible replies, all sessions
    auth_model = defaultdict(lambda: defaultdict(int))   # authoritative per-model totals
    cost, cost_complete, minutes_cs, notes = 0.0, True, 0.0, []
    for sid in sids:
        files = session_files(pdir, sid)
        if not files:
            print(f"warning: no log files for session {sid}", file=sys.stderr)
        st = Totals()
        collect(files, st)
        collect(files, totals)
        totals.sessions.append(sid)
        main_file = pdir / f"{sid}.jsonl"
        cs = read_cost_state(main_file) if main_file.exists() else None
        if cs is None:
            cost_complete = False
            notes.append(f"{sid[:8]}: no cost-state in log, counted replies only (lower bound)")
            for m, u in st.by_model.items():
                for f in FIELDS:
                    auth_model[m][f] += u[f]
            continue
        cost += cs["cost"]
        minutes_cs += cs["minutes"]
        cost_complete &= not cs["unknown_cost"]
        vis_all = sum_fields(st.by_agent)
        cs_all = sum_fields(cs["by_model"])
        covers = all(vis_all[f] <= cs_all[f] * 1.01 + 10 for f in FIELDS)
        for m, u in cs["by_model"].items():
            for f in FIELDS:
                auth_model[m][f] += u[f]
        if not covers:  # cost-state counted the main thread only: add subagent replies on top
            cost_complete = False
            notes.append(f"{sid[:8]}: cost-state excludes subagents; their reply tokens were added, their cost is not included")
            for k, u in st.by_agent.items():
                if k != "main session":
                    for f in FIELDS:
                        auth_model["(subagents)"][f] += u[f]

    vis_grand = sum_fields(totals.by_agent)
    grand = sum_fields(auth_model)
    background = {f: max(0, grand[f] - vis_grand[f]) for f in FIELDS}
    by_agent = {k: dict(v) for k, v in totals.by_agent.items()}
    if sum(background.values()):
        by_agent[BACKGROUND] = background
    minutes = minutes_cs or ((totals.last - totals.first).total_seconds() / 60 if totals.first and totals.last else 0)
    total_all = sum(grand.values())
    sub_total = sum(sum(u.values()) for k, u in totals.by_agent.items() if k != "main session")
    calls = sum(totals.calls.values())
    cost_txt = (f"${cost:.2f}" + ("" if cost_complete else " (partial)")) if cost else "n/a"

    if a.json:
        print(json.dumps({"label": a.label, "sessions": totals.sessions, "minutes": round(minutes, 1),
                          "cost_usd": round(cost, 4), "cost_complete": cost_complete,
                          "totals": dict(grand), "all_tokens": total_all, "subagent_tokens": sub_total,
                          "background": background, "calls": calls, "notes": notes,
                          "by_agent": by_agent,
                          "by_model": {k: dict(v) for k, v in auth_model.items()}}, indent=2))
        return 0

    head = "| {} | input | cache write | cache read | output | all tokens |"
    sep = "|---|---|---|---|---|---|"
    print(f"## Tokens · {a.label}\n")
    print(f"Sessions: {len(totals.sessions)} · logged model replies: {calls} · "
          f"time: {minutes:.0f} min · **cost: {cost_txt}**\n")
    for n in notes:
        print(f"- note: {n}")
    print("### By agent\n")
    print("| agent | calls | input | cache write | cache read | output | all tokens |")
    print("|---|---|---|---|---|---|---|")
    for k, u in sorted(by_agent.items(), key=lambda kv: (kv[0] == BACKGROUND, -sum(kv[1].values()))):
        print(row(k, u, totals.calls.get(k, "-") if k != BACKGROUND else "-"))
    print(row("**total**", grand, calls))
    print("\n### By model (Claude Code's own totals, same as /cost)\n")
    print(head.format("model")); print(sep)
    for k, u in sorted(auth_model.items(), key=lambda kv: -sum(kv[1].values())):
        print(row(k, u))
    print("\n### Summary row for bench/results.md\n")
    print(f"| {a.label} | {fmt(total_all)} | {fmt(grand['output_tokens'])} | "
          f"{fmt(grand['cache_read_input_tokens'])} | {fmt(sub_total)} | {calls} | "
          f"{minutes:.0f} min | {cost_txt} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
