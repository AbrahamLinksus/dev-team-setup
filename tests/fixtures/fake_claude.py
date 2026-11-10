#!/usr/bin/env python3
"""Stand-in for the `claude` CLI, used by test_bench.py. It writes session logs in the
same format Claude Code 2.1.312 does (assistant replies with usage, AskUserQuestion,
subagent logs, cost-state lines) and "builds" the small fixture app."""
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOGS = Path(os.environ["BENCH_LOGS"])
PROJECTS = Path(os.environ["BENCH_PROJECTS"])
STATE = Path(os.environ["FAKE_CLAUDE_STATE"])
APP = Path(__file__).with_name("small_app")
args = sys.argv[1:]


def plugin_on() -> bool:
    return not STATE.exists() or STATE.read_text() != "disabled"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def usage(i, cw, cr, o):
    return {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": o}


def write_session(cwd: Path, prompt: str, replies, cost, model_usage, ask=False, typed=0, subagent=None):
    d = LOGS / re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))
    d.mkdir(parents=True, exist_ok=True)
    sid = str(uuid.uuid4())
    lines = [{"type": "user", "timestamp": now(), "message": {"role": "user", "content": prompt}},
             {"type": "user", "timestamp": now(), "isMeta": True, "message": {"content": "<command-name>/model</command-name>"}}]
    for n, u in enumerate(replies):
        content = [{"type": "text", "text": "working"}]
        if ask and n == 0:
            content.append({"type": "tool_use", "id": f"toolu_{sid[:6]}", "name": "AskUserQuestion", "input": {}})
        for _ in range(2):  # Claude Code logs one reply across several lines
            lines.append({"type": "assistant", "timestamp": now(), "requestId": f"req_{sid[:6]}_{n}",
                          "message": {"id": f"msg_{sid[:6]}_{n}", "model": "claude-opus-5-5", "usage": u, "content": content}})
        if ask and n == 0:
            lines.append({"type": "user", "timestamp": now(), "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"toolu_{sid[:6]}", "content": "Approve"}]}})
    for _ in range(typed):
        lines.append({"type": "user", "timestamp": now(), "message": {"content": "looks good, continue"}})
    lines.append({"type": "cost-state", "sessionId": sid, "totalCostUSD": cost, "totalDuration": 120000,
                  "hasUnknownModelCost": False, "modelUsage": {
                      m: {"inputTokens": u[0], "cacheCreationInputTokens": u[1], "cacheReadInputTokens": u[2],
                          "outputTokens": u[3], "thinkingTokens": 0, "costUSD": 0} for m, u in model_usage.items()}})
    (d / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    if subagent:
        sd = d / sid / "subagents"
        sd.mkdir(parents=True)
        (sd / "agent-a1.jsonl").write_text("\n".join(json.dumps(x) for x in [
            {"type": "user", "timestamp": now(), "message": {"content": "BRIEF · T-01 · backend-coder · implement"}},
            {"type": "assistant", "timestamp": now(), "message": {"id": f"sub_{sid[:6]}", "model": "claude-sonnet-5-5",
                                                                  "usage": subagent}}]) + "\n")


if args[:1] == ["--version"]:
    print("2.1.312 (Claude Code)")
elif args[:1] == ["plugin"]:
    sub = args[1] if len(args) > 1 else ""
    if sub == "list":
        print(f"  > dev-team-setup@dev-team-setup\n    Status: {'enabled' if plugin_on() else 'disabled'}")
    elif sub in ("enable", "disable"):
        STATE.write_text("enabled" if sub == "enable" else "disabled")
        print(f"Successfully {sub}d plugin")
elif "-p" in args:
    prompt = args[args.index("-p") + 1]
    if prompt == "Reply with just: ok":
        total = 28677 + (5562 if plugin_on() else 0)
        print(json.dumps({"is_error": False, "result": "ok", "usage": usage(3, 0, total - 3, 4)}))
    elif "Answers file:" in prompt:  # unattended plugin session (D7): answer cards into answers.log
        log = Path(re.search(r"Answers file: (.+)", prompt).group(1).strip()).with_name("answers.log")
        m = re.search(r"Name the repo ([\w-]+)", prompt) or re.search(r"resume ([\w-]+)", prompt)
        repo = PROJECTS / m.group(1)
        if not repo.exists():
            shutil.copytree(APP, repo)
        lines = (["2026-11-10T10:00 · Spec · Approve the spec? → Approve",
                  "2026-11-10T10:05 · T-01 · Approve T-01? → Approve", "MILESTONE DONE 1"]
                 if "resume" not in prompt else
                 ["2026-11-10T10:20 · Handover · Approve the handover? → Approve", "HANDOVER DONE"])
        with log.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        write_session(Path.cwd(), prompt, [usage(5, 3000, 50000, 900)], 2.5,
                      {"claude-opus-5-5": (500, 9000, 400000, 3000), "claude-sonnet-5-5": (10, 2000, 30000, 700)},
                      subagent=usage(10, 2000, 30000, 700))
        print(json.dumps({"is_error": False, "result": "done", "total_cost_usd": 2.5}))
    else:  # a normal build: "write" the app and log the session
        STATE.with_name("plugin-during-build").write_text("on" if plugin_on() else "off")
        cwd = Path.cwd()
        for f in APP.iterdir():
            shutil.copy(f, cwd / f.name)
        write_session(cwd, prompt, [usage(2, 20862, 25156, 169), usage(28, 16003, 672643, 12692)], 0.758604,
                      {"claude-opus-5-5": (1159, 38308, 932061, 13045), "claude-haiku-5-5": (1238, 0, 0, 136)})
        print(json.dumps({"is_error": False, "result": "done", "total_cost_usd": 0.758604}))
else:  # interactive session (plugin run)
    prompt = args[0] if args else ""
    m = re.search(r"Name the repo (\S+?)\.?$", prompt) or re.search(r"resume (\S+)", prompt)
    repo = PROJECTS / (m.group(1) if m else "unknown")
    if not repo.exists():
        shutil.copytree(APP, repo)
    write_session(Path.cwd(), prompt, [usage(5, 3000, 50000, 900)], 2.5,
                  {"claude-opus-5-5": (500, 9000, 400000, 3000), "claude-sonnet-5-5": (10, 2000, 30000, 700)},
                  ask=True, typed=1, subagent=usage(10, 2000, 30000, 700))
