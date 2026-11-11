#!/usr/bin/env python3
"""Read Claude Code's session logs: tokens, cost and owner interventions per session.

Claude Code logs each session to ~/.claude/projects/<folder with non-alphanumerics as ->/<id>.jsonl,
with subagents under <id>/subagents/. The last `cost-state` line of a session holds the same totals
as /cost. cost.py uses this for the result card's Cost line and the budget cap.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Where Claude Code keeps its session logs. DEVTEAM_LOGS overrides it (tests use it).
_CONFIG = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
LOGS = Path(os.environ.get("DEVTEAM_LOGS") or _CONFIG / "projects")

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
CAMEL = {"inputTokens": "input_tokens", "cacheCreationInputTokens": "cache_creation_input_tokens",
         "cacheReadInputTokens": "cache_read_input_tokens", "outputTokens": "output_tokens"}
BRIEF_RE = re.compile(r"BRIEF\s*·\s*(\S+)\s*·\s*([a-z][a-z0-9-]+)(?:\s*·\s*([a-z][a-z-]*))?")
# Price weight of each token type relative to fresh input (cache read 0.1×, cache write
# 1.25×, output 5×), so shares say where the money goes, not just where the tokens go.
WEIGHTS = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1,
           "output_tokens": 5.0}


def weighted(u: dict) -> float:
    return sum(WEIGHTS[f] * u.get(f, 0) for f in FIELDS)


def brief_step(path: Path) -> str | None:
    """The step a subagent ran (implement, test, review, debug, …) from its BRIEF line."""
    for d in read_lines(path):
        if d.get("type") == "user" and isinstance(d.get("message"), dict):
            m = BRIEF_RE.search(text_of(d["message"]))
            return m.group(3) if m and m.group(3) else None
    return None


BACKGROUND = "background calls (not logged as replies)"
NOT_TYPED = ("<command-", "<local-command", "Caveat:", "[Request interrupted", "<system-reminder")


def log_dir_for(folder: Path) -> Path:
    return LOGS / re.sub(r"[^A-Za-z0-9]", "-", str(folder.resolve()))


def read_lines(path: Path):
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def parse_ts(s) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.astimezone()
    except ValueError:
        return None


def text_of(message: dict) -> str:
    c = message.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def agent_label(path: Path) -> str:
    meta = path.with_suffix(".meta.json")
    if meta.exists():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
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


def sessions_in(log_dir: Path, since: datetime | None) -> list[str]:
    out = []
    for p in sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        first = next((parse_ts(d.get("timestamp")) for d in read_lines(p) if d.get("timestamp")), None)
        if since is None or (first and first >= since):
            out.append(p.stem)
    return out


def measure(log_dir: Path, sessions: list[str]) -> dict:
    """Totals from Claude Code's own accounting (last cost-state per session = /cost); split by
    agent from logged replies; remainder shown as background calls. Also counts interventions."""
    by_agent = defaultdict(lambda: defaultdict(int))
    by_step = defaultdict(lambda: defaultdict(int))
    calls = defaultdict(int)
    auth = defaultdict(lambda: defaultdict(int))
    cost, cost_complete, minutes, notes = 0.0, True, 0.0, []
    typed = asked = 0
    first = last = None
    for sid in sessions:
        main = log_dir / f"{sid}.jsonl"
        files: list[tuple[Path, str | None]] = [(main, None)] if main.exists() else []
        if (log_dir / sid).is_dir():   # subagent logs live in <session-id>/…
            files += [(p, agent_label(p)) for p in sorted((log_dir / sid).rglob("*.jsonl"))]
        s_agent = defaultdict(lambda: defaultdict(int))
        s_model = defaultdict(lambda: defaultdict(int))
        for path, fixed in files:
            replies, ask_ids, prompts = {}, set(), 0
            step = "orchestrator" if fixed is None else (brief_step(path) or "other")
            for i, d in enumerate(read_lines(path)):
                ts = parse_ts(d.get("timestamp"))
                if ts:
                    first = ts if first is None or ts < first else first
                    last = ts if last is None or ts > last else last
                msg = d.get("message") if isinstance(d.get("message"), dict) else None
                if fixed is None and d.get("type") == "user" and msg and not d.get("isMeta") and not d.get("isSidechain"):
                    t = text_of(msg).strip()
                    if t and not t.startswith(NOT_TYPED):
                        prompts += 1
                if d.get("type") != "assistant" or not msg:
                    continue
                if fixed is None and not d.get("isSidechain"):
                    for b in msg.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                            ask_ids.add(b.get("id") or f"{i}")
                u = msg.get("usage")
                if not u:
                    continue
                key = msg.get("id") or d.get("requestId") or f"{path}:{i}"
                agent = fixed or ("subagent (sidechain)" if d.get("isSidechain") else "main session")
                prev = replies.get(key)
                if prev is None or int(u.get("output_tokens") or 0) >= int(prev[2].get("output_tokens") or 0):
                    replies[key] = (agent, msg.get("model", "unknown"), u)
            for agent, model, u in replies.values():
                calls[agent] += 1
                for f in FIELDS:
                    v = int(u.get(f) or 0)
                    by_agent[agent][f] += v
                    by_step[step if agent != "subagent (sidechain)" else "other"][f] += v
                    s_agent[agent][f] += v
                    s_model[model][f] += v
            if fixed is None:
                typed += max(0, prompts - 1)      # the first prompt of each session is the launch prompt
                asked += len(ask_ids)
        cs = None
        if main.exists():
            for d in read_lines(main):
                if d.get("type") == "cost-state" and isinstance(d.get("modelUsage"), dict):
                    cs = d
        if cs is None:
            cost_complete = False
            notes.append(f"session {sid[:8]}: no cost-state in log; counted replies only (lower bound)")
            for m, u in s_model.items():
                for f in FIELDS:
                    auth[m][f] += u[f]
            continue
        cost += float(cs.get("totalCostUSD") or 0)
        minutes += (cs.get("totalDuration") or 0) / 60000
        cost_complete &= not cs.get("hasUnknownModelCost")
        cs_model = {m: {f: int(u.get(c) or 0) for c, f in CAMEL.items()} for m, u in cs["modelUsage"].items()}
        vis = {f: sum(u[f] for u in s_agent.values()) for f in FIELDS}
        cs_sum = {f: sum(u[f] for u in cs_model.values()) for f in FIELDS}
        for m, u in cs_model.items():
            for f in FIELDS:
                auth[m][f] += u[f]
        if not all(vis[f] <= cs_sum[f] * 1.01 + 10 for f in FIELDS):
            cost_complete = False
            notes.append(f"session {sid[:8]}: cost-state excludes subagents; their reply tokens were added")
            for k, u in s_agent.items():
                if k != "main session":
                    for f in FIELDS:
                        auth["(subagents)"][f] += u[f]
    grand = {f: sum(u[f] for u in auth.values()) for f in FIELDS}
    vis_grand = {f: sum(u[f] for u in by_agent.values()) for f in FIELDS}
    background = {f: max(0, grand[f] - vis_grand[f]) for f in FIELDS}
    agents = {k: dict(v) for k, v in by_agent.items()}
    if sum(background.values()):
        agents[BACKGROUND] = background
    if not minutes and first and last:
        minutes = (last - first).total_seconds() / 60
    return {"sessions": sessions, "cost_usd": round(cost, 4), "cost_complete": cost_complete,
            "tokens": grand, "all_tokens": sum(grand.values()),
            "subagent_tokens": sum(sum(u.values()) for k, u in by_agent.items() if k != "main session"),
            "calls": sum(calls.values()), "minutes": round(minutes, 1), "background": background,
            "by_agent": agents, "agent_calls": dict(calls), "by_step": {k: dict(v) for k, v in by_step.items()},
            "shares": shares(agents),
            "by_model": {k: dict(v) for k, v in auth.items()},
            "interventions": typed + asked, "typed": typed, "answered_questions": asked, "notes": notes}


def shares(groups: dict) -> dict:
    """Per group: share of the run's price-weighted cost, how much of its input was written to the
    cache rather than read from it, and its output share of its own cost."""
    total = sum(weighted(u) for u in groups.values()) or 1.0
    out = {}
    for k, u in groups.items():
        cached = u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        w = weighted(u) or 1.0
        out[k] = {"cost_share": round(weighted(u) / total, 4),
                  "cache_write_share": round(u.get("cache_creation_input_tokens", 0) / cached, 4) if cached else 0.0,
                  "output_cost_share": round(5.0 * u.get("output_tokens", 0) / w, 4)}
    return out
