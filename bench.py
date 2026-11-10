#!/usr/bin/env python3
"""bench.py: compare a normal Claude Code session with the /setup-project plugin.

One file, standard library only. It builds the same app twice (normal session, then the
plugin), measures tokens, cost, time and how often you had to step in, starts each build
and tests it from the outside, checks code quality, and writes ~/bench/results.md.

    python3 bench.py all                 guided run of everything (safe to stop and re-run)
    python3 bench.py check               check the tools you need
    python3 bench.py clean [--github]    delete data from earlier benchmark runs (asks first)
    python3 bench.py overhead            what the installed plugin adds to every model call
    python3 bench.py run small normal    one run: app = small | production, mode = normal | plugin
    python3 bench.py report              rebuild ~/bench/results.md from what has run
    python3 bench.py tokens [--since T]  token/cost report for the session logs of the current folder

Two apps: "small" (link shortener API, 8 acceptance checks) and "production" (issue
tracker with accounts, permissions, web UI, Docker, CI: 29 acceptance checks).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---- settings (environment overrides are used by the tests) ---------------------------------
HOME = Path.home()
BENCH = Path(os.environ.get("BENCH_DIR", HOME / "bench"))
PROJECTS = Path(os.environ.get("BENCH_PROJECTS", HOME / "projects"))
LOGS = Path(os.environ.get("BENCH_LOGS", HOME / ".claude" / "projects"))
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
PORT = int(os.environ.get("BENCH_PORT", "8000"))
PLUGIN = "dev-team-setup@dev-team-setup"
STATE = BENCH / "state.json"
RESULTS = BENCH / "results.md"

# ---- the two apps ---------------------------------------------------------------------------
RUN_SECTION = """
## How it's started
`./start.sh` in the project root installs what it needs (e.g. `uv sync`) and starts the API on
port 8000 (or `$PORT` if set). Data is kept in a local database file, so it survives a restart.
"""

SMALL_SPEC = """# Small benchmark: link shortener API

## What it does
| Endpoint | Behaviour |
|---|---|
| `POST /links` with `{"url": "https://example.com/page"}` | `201` → `{"code": "aZ3k9Q", "short_url": "http://localhost:8000/aZ3k9Q"}`. Invalid URL → `422`. |
| `GET /{code}` | `307` redirect to the original URL and +1 click. Unknown code → `404`. |
| `GET /links/{code}/stats` | `200` → `{"url": "...", "clicks": 3, "created_at": "2026-11-09T10:00:00Z"}`. Unknown → `404`. |

- Codes: 6 characters, `[A-Za-z0-9]`, unique.
- Data is stored in SQLite and survives a restart.

## Stack (fixed)
Python 3.12+, FastAPI, SQLite via the standard library `sqlite3`, `uv` for the project,
`pytest` + `pytest-cov`, `ruff`, `mypy --strict`. Allowed extras: `uvicorn` (to run the app)
and `httpx` (for FastAPI's test client). No other packages.

## Quality bar
- Tests for every endpoint, including the error cases.
- Coverage ≥ 85%.
- `ruff check` and `mypy --strict` pass with no errors.
- Layered code: routes → service → repository (SQLite).
- `README.md` explains how to install, run and test it.
- `start.sh` as described below.
""" + RUN_SECTION + """
## Not included
Auth, custom codes, expiry, a web UI, deployment.
"""

PRODUCTION_SPEC = """# Production benchmark: team issue tracker

A multi-user issue tracker: an API with accounts, permissions and pagination, plus a small
web UI, packaged like a real service (Docker, CI, migrations, logging).

## API contract
All bodies are JSON. Every endpoint except `/health`, `/auth/register` and `/auth/login`
needs `Authorization: Bearer <token>`; missing or invalid token → `401`.

| Request | Response |
|---|---|
| `GET /health` | `200 {"status": "ok"}` |
| `POST /auth/register {"email", "password"}` | `201 {"id", "email"}` · email already used → `409` · invalid email or password under 8 characters → `422` |
| `POST /auth/login {"email", "password"}` | `200 {"access_token", "token_type": "bearer"}` · wrong email or password → `401` |
| `POST /projects {"name"}` | `201 {"id", "name", "owner_id"}` · the creator is the owner |
| `GET /projects` | `200 [project, …]`: projects the user owns or is a member of |
| `POST /projects/{id}/members {"email"}` | `201 {"user_id", "project_id"}` · only the owner may add (member → `403`) · unknown email → `404` |
| `POST /projects/{id}/issues {"title", "description"?, "priority"?, "assignee_id"?}` | `201 issue` · empty title → `422` · assignee who isn't owner/member → `422` |
| `GET /projects/{id}/issues?status=&priority=&page=1&page_size=20` | `200 {"items": [issue, …], "total", "page", "page_size"}` · newest first · `page_size` max 100 |
| `PATCH /issues/{id}` with any of `title, description, status, priority, assignee_id` | `200 issue` · invalid status or priority → `422` |
| `DELETE /issues/{id}` | `204` · only the project owner (member → `403`) |
| `POST /issues/{id}/comments {"body"}` | `201 {"id", "issue_id", "author_id", "body", "created_at"}` · empty body → `422` |
| `GET /issues/{id}/comments` | `200 [comment, …]`, oldest first |

- Issue: `{"id", "project_id", "title", "description", "status", "priority", "assignee_id", "created_at", "updated_at"}`;
  `status` is `open` | `in_progress` | `done` (new issues are `open`); `priority` is `low` | `medium` | `high` (default `medium`).
- A user who is neither owner nor member gets `404` for anything under that project.
- Login rate limit: after 5 failed logins for the same email within 60 seconds, further login
  attempts for that email return `429` until the minute has passed.

## Web UI
Register and log in · projects page (list, create) · project page (issue list with a status
filter, create an issue, change status, open an issue and add a comment) · works at 390 px
wide and on desktop.

## Stack (fixed)
- API: Python 3.12+, FastAPI, uvicorn, SQLAlchemy 2.x, Alembic, PyJWT, argon2 or bcrypt,
  pydantic-settings. SQLite locally and in tests; PostgreSQL in Docker Compose. `uv`.
- Web: React + Vite + TypeScript, ESLint, Vitest + Testing Library.
- Tooling: pytest + pytest-cov (+ httpx), ruff, mypy `--strict`.

## Quality bar
- Every endpoint tested, including error and permission cases. API coverage ≥ 85%.
- `ruff check` and `mypy --strict` pass. ESLint, the TypeScript build and Vitest pass.
- Layered API: routes → services → repositories; database access only in repositories.
- Passwords hashed, secrets only from environment variables, `.env.example` provided.
- Structured (JSON) logs with a request id on every request.
- `Dockerfile` for the API and `docker-compose.yml` (api + postgres + web).
- GitHub Actions workflow running the API and web checks.
- `README.md`: run locally and with Docker, test, short architecture overview.
- `start.sh` as described below (API only).
""" + RUN_SECTION + """
## Not included
Email verification, password reset, refresh tokens, real-time updates, file uploads,
deployment to a cloud provider.
"""

ANSWERS = """# How to answer the plugin ({app} benchmark)

Answer the same way every run, so runs are comparable. bench.py counts your answers itself.

| When the plugin asks… | Answer |
|---|---|
| Repo name / visibility | `{repo}` · Private |
| Spec questions | Answer from spec.md. If it doesn't say, pick the (Recommended) option |
| "Decide for me" offered and spec.md is silent | Decide for me |
| Spec, HLD, team, LLD, install, task-list cards | Approve (add no optional agents) |
| Stack / package cards | Whatever matches spec.md's Stack section; otherwise (Recommended) |
| Task result cards | Approve if every goal is ✅. If a goal is ❌: Request changes once, "fix the ❌ goal" |
| Milestone card | Approve + continue in a fresh session, then /exit (bench.py restarts it for you) |
| "Fix or change request?" | Fix to this task |
| Handover card | Approve, then /exit |
"""

APPS = {
    "small": {"repo": "bench-link-shortener", "spec": SMALL_SPEC, "checks": 8},
    "production": {"repo": "bench-issue-tracker", "spec": PRODUCTION_SPEC, "checks": 29},
}
NORMAL_PROMPT = ('Build the app described in spec.md in this folder. Work until every item in '
                 '"Quality bar" is met, then stop and give me a short summary.')
# Plain words rather than a slash command: plugin skills can be namespaced
# (/dev-team-setup:setup-project), and asking for the skill by name works either way.
PLUGIN_PROMPT = ("Use the setup-project skill (/setup-project) to build the app described in spec.md in this "
                 "folder. Treat spec.md as the full requirements and answer spec questions from it. "
                 "Name the repo {repo}.")
RESUME_PROMPT = "Use the setup-project skill (/setup-project) to resume {repo}"


# ---- small helpers --------------------------------------------------------------------------
def say(msg: str = "") -> None:
    print(msg, flush=True)


def ask(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        ans = input(f"{question}{hint} ").strip()
    except EOFError:
        ans = ""
    return ans or default


def yes(question: str, default: bool = True) -> bool:
    return ask(question + (" (Y/n)" if default else " (y/N)"), "y" if default else "n").lower().startswith("y")


def run(cmd: list[str], cwd: Path | None = None, timeout: int | None = None, env: dict | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **(env or {})})
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    BENCH.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


# ---- session logs: tokens, cost, interventions -----------------------------------------------
FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
CAMEL = {"inputTokens": "input_tokens", "cacheCreationInputTokens": "cache_creation_input_tokens",
         "cacheReadInputTokens": "cache_read_input_tokens", "outputTokens": "output_tokens"}
BRIEF_RE = re.compile(r"BRIEF\s*·\s*(\S+)\s*·\s*([a-z][a-z0-9-]+)(?:\s*·\s*([a-z][a-z-]*))?")
# D9: price weight of each token type relative to fresh input (cache read 0.1×, cache write
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
    cache rather than read from it (H3), and its output share of its own cost (H4)."""
    total = sum(weighted(u) for u in groups.values()) or 1.0
    out = {}
    for k, u in groups.items():
        cached = u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        w = weighted(u) or 1.0
        out[k] = {"cost_share": round(weighted(u) / total, 4),
                  "cache_write_share": round(u.get("cache_creation_input_tokens", 0) / cached, 4) if cached else 0.0,
                  "output_cost_share": round(5.0 * u.get("output_tokens", 0) / w, 4)}
    return out


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def token_table(m: dict, label: str) -> str:
    rows = [f"## Tokens · {label}", "",
            f"Sessions: {len(m['sessions'])} · logged replies: {m['calls']} · time: {m['minutes']:.0f} min · "
            f"cost: ${m['cost_usd']:.2f}{'' if m['cost_complete'] else ' (partial)'} · "
            f"interventions: {m['interventions']} ({m['typed']} typed, {m['answered_questions']} answered)", ""]
    rows += [f"- note: {n}" for n in m["notes"]]
    sh = m.get("shares") or shares(m["by_agent"])
    rows += ["| agent | calls | input | cache write | cache read | output | all | cost share "
             "| cached input written | output share of cost |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, u in sorted(m["by_agent"].items(), key=lambda kv: (kv[0] == BACKGROUND, -sum(kv[1].values()))):
        x = sh.get(k) or {"cost_share": 0, "cache_write_share": 0, "output_cost_share": 0}
        rows.append(f"| {k} | {m['agent_calls'].get(k, '-')} | " + " | ".join(fmt(u[f]) for f in FIELDS)
                    + f" | {fmt(sum(u.values()))} | {pct(x['cost_share'])} | {pct(x['cache_write_share'])}"
                    + f" | {pct(x['output_cost_share'])} |")
    t = m["tokens"]
    rows.append(f"| **total** | {m['calls']} | " + " | ".join(fmt(t[f]) for f in FIELDS)
                + f" | {fmt(m['all_tokens'])} | | | |")
    if len(m.get("by_step") or {}) > 1:
        ss = shares(m["by_step"])
        rows += ["", "| step | input | cache write | cache read | output | cost share | output share of cost |",
                 "|---|---|---|---|---|---|---|"]
        for k, u in sorted(m["by_step"].items(), key=lambda kv: -weighted(kv[1])):
            rows.append(f"| {k} | " + " | ".join(fmt(u.get(f, 0)) for f in FIELDS)
                        + f" | {pct(ss[k]['cost_share'])} | {pct(ss[k]['output_cost_share'])} |")
    return "\n".join(rows)


# ---- acceptance tests (outside-in, identical for both builds) -----------------------------------
class Http:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        self.opener = urllib.request.build_opener(NoRedirect)

    def __call__(self, method: str, path: str, body=None, token: str | None = None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            r = self.opener.open(req, timeout=15)
            raw, st, hd = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            raw, st, hd = e.read(), e.code, e.headers
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return 0, {}, None          # hung, refused or dropped: the check fails, the run goes on
        try:
            return st, hd, json.loads(raw) if raw else None
        except ValueError:
            return st, hd, None


def accept_small(base: str) -> tuple[list, dict]:
    h, res = Http(base), []
    st, _, created = h("POST", "/links", {"url": "https://example.com/page"})
    created = created if isinstance(created, dict) else {}
    code = str(created.get("code", ""))
    res.append(("POST /links valid URL → 201", st == 201))
    res.append(("code is 6 chars [A-Za-z0-9]", bool(re.fullmatch(r"[A-Za-z0-9]{6}", code))))
    res.append(("short_url ends with the code", bool(code) and str(created.get("short_url", "")).endswith(code)))
    st, _, _ = h("POST", "/links", {"url": "not a url"})
    res.append(("POST /links invalid URL → 422", st == 422))
    st, hd, _ = h("GET", f"/{code}")
    res.append(("GET /{code} → 307 to the original URL", st == 307 and (hd or {}).get("Location") == "https://example.com/page"))
    h("GET", f"/{code}")
    st, _, stats = h("GET", f"/links/{code}/stats")
    stats = stats if isinstance(stats, dict) else {}
    res.append(("stats → 200 with url and created_at", st == 200 and stats.get("url") == "https://example.com/page"
                and bool(stats.get("created_at"))))
    res.append(("clicks counted (2 redirects → 2)", stats.get("clicks") == 2))
    st1, _, _ = h("GET", "/zzzzzz")
    st2, _, _ = h("GET", "/links/zzzzzz/stats")
    res.append(("unknown code → 404 (redirect and stats)", st1 == 404 and st2 == 404))
    return res, {"code": code}


def persist_small(base: str, ctx: dict) -> bool:
    st, _, stats = Http(base)("GET", f"/links/{ctx.get('code')}/stats")
    return st == 200 and isinstance(stats, dict) and stats.get("clicks") == 2


def accept_production(base: str) -> tuple[list, dict]:
    h, res, run_id = Http(base), [], secrets.token_hex(4)
    pw = "correct-horse-1"

    def chk(name, ok):
        res.append((name, bool(ok)))

    def login(email, password=pw):
        st, _, b = h("POST", "/auth/login", {"email": email, "password": password})
        return st, (b or {}).get("access_token") if isinstance(b, dict) else None

    def user(tag):
        email = f"{tag}-{run_id}@example.com"
        h("POST", "/auth/register", {"email": email, "password": pw})
        return email, login(email)[1]

    st, _, b = h("GET", "/health")
    chk("GET /health → 200 {status: ok}", st == 200 and isinstance(b, dict) and b.get("status") == "ok")
    email_a = f"alice-{run_id}@example.com"
    st, _, b = h("POST", "/auth/register", {"email": email_a, "password": pw})
    chk("register → 201 with id and email", st == 201 and isinstance(b, dict) and b.get("email") == email_a and "id" in b)
    st, _, _ = h("POST", "/auth/register", {"email": email_a, "password": pw})
    chk("register same email → 409", st == 409)
    st1, _, _ = h("POST", "/auth/register", {"email": f"short-{run_id}@example.com", "password": "short"})
    st2, _, _ = h("POST", "/auth/register", {"email": "not-an-email", "password": pw})
    chk("register bad password / bad email → 422", st1 == 422 and st2 == 422)
    st, _, b = h("POST", "/auth/login", {"email": email_a, "password": pw})
    ta = b.get("access_token") if isinstance(b, dict) else None
    chk("login → 200 bearer token", st == 200 and ta and str(b.get("token_type", "")).lower() == "bearer")
    st, _ = login(email_a, "wrong-password")
    chk("login wrong password → 401", st == 401)
    st1, _, _ = h("GET", "/projects")
    st2, _, _ = h("GET", "/projects", token="not-a-real-token")
    chk("no or invalid token → 401", st1 == 401 and st2 == 401)

    email_b, tb = user("bob")
    email_c, tc = user("carol")
    st, _, proj = h("POST", "/projects", {"name": f"Bench {run_id}"}, ta)
    proj = proj if isinstance(proj, dict) else {}
    pid = proj.get("id")
    chk("create project → 201, creator is owner", st == 201 and pid is not None and proj.get("owner_id") is not None)
    st, _, lst = h("GET", "/projects", token=ta)
    chk("owner sees project in GET /projects", st == 200 and any(isinstance(p, dict) and p.get("id") == pid for p in (lst or [])))
    st, _, _ = h("GET", f"/projects/{pid}/issues", token=tb)
    chk("non-member → 404 on project issues", st == 404)
    st, _, _ = h("POST", f"/projects/{pid}/members", {"email": email_b}, ta)
    chk("owner adds member → 201", st == 201)
    st, _, _ = h("POST", f"/projects/{pid}/members", {"email": f"ghost-{run_id}@example.com"}, ta)
    chk("add unknown email → 404", st == 404)
    st, _, _ = h("POST", f"/projects/{pid}/members", {"email": email_c}, tb)
    chk("member adds member → 403", st == 403)
    st, _, lst = h("GET", "/projects", token=tb)
    chk("member sees project in GET /projects", st == 200 and any(isinstance(p, dict) and p.get("id") == pid for p in (lst or [])))

    st, _, issue = h("POST", f"/projects/{pid}/issues", {"title": "First bug", "description": "It breaks"}, tb)
    issue = issue if isinstance(issue, dict) else {}
    iid = issue.get("id")
    chk("member creates issue → 201, open, medium", st == 201 and issue.get("status") == "open" and issue.get("priority") == "medium")
    st, _, _ = h("POST", f"/projects/{pid}/issues", {"title": ""}, ta)
    chk("empty title → 422", st == 422)
    st, _, _ = h("POST", f"/projects/{pid}/issues", {"title": "Assigned", "assignee_id": 10**9}, ta)
    chk("assignee who isn't a member → 422", st == 422)
    for n in range(3):
        h("POST", f"/projects/{pid}/issues", {"title": f"Issue {n}", "priority": "high"}, ta)
    st, _, page = h("GET", f"/projects/{pid}/issues?page=1&page_size=2", token=ta)
    page = page if isinstance(page, dict) else {}
    items = page.get("items") or []
    chk("list is paginated (items, total, page, page_size)", st == 200 and len(items) == 2 and page.get("total") == 4
        and page.get("page") == 1 and page.get("page_size") == 2)
    chk("list is newest first", len(items) == 2 and isinstance(items[0], dict) and items[0].get("title") == "Issue 2")
    st, _, page = h("GET", f"/projects/{pid}/issues?priority=high", token=ta)
    chk("filter by priority", st == 200 and isinstance(page, dict) and page.get("total") == 3)
    st, _, upd = h("PATCH", f"/issues/{iid}", {"status": "in_progress"}, tb)
    chk("PATCH status → 200 in_progress", st == 200 and isinstance(upd, dict) and upd.get("status") == "in_progress")
    st, _, _ = h("PATCH", f"/issues/{iid}", {"status": "finished"}, tb)
    chk("PATCH invalid status → 422", st == 422)
    st, _, page = h("GET", f"/projects/{pid}/issues?status=in_progress", token=ta)
    chk("filter by status", st == 200 and isinstance(page, dict) and page.get("total") == 1)
    st, _, _ = h("PATCH", f"/issues/{iid}", {"status": "done"}, tc)
    chk("non-member PATCH → 404", st == 404)

    st1, _, c1 = h("POST", f"/issues/{iid}/comments", {"body": "Looking into it"}, ta)
    h("POST", f"/issues/{iid}/comments", {"body": "Fixed locally"}, tb)
    st2, _, _ = h("POST", f"/issues/{iid}/comments", {"body": ""}, ta)
    chk("comment → 201; empty body → 422", st1 == 201 and isinstance(c1, dict) and c1.get("body") == "Looking into it" and st2 == 422)
    st, _, cs = h("GET", f"/issues/{iid}/comments", token=tb)
    chk("comments listed oldest first", st == 200 and [c.get("body") for c in (cs or []) if isinstance(c, dict)]
        == ["Looking into it", "Fixed locally"])

    st, _, _ = h("DELETE", f"/issues/{iid}", token=tb)
    chk("member DELETE → 403", st == 403)
    st, _, _ = h("DELETE", f"/issues/{iid}", token=ta)
    st2, _, page = h("GET", f"/projects/{pid}/issues", token=ta)
    chk("owner DELETE → 204 and it's gone", st == 204 and isinstance(page, dict) and page.get("total") == 3)

    codes = [login(email_c, "wrong-password")[0] for _ in range(5)]
    st, _ = login(email_c)
    chk("5 failed logins → 6th attempt 429", codes == [401] * 5 and st == 429)
    return res, {"email": email_a, "project_id": pid}


def persist_production(base: str, ctx: dict) -> bool:
    h = Http(base)
    st, _, b = h("POST", "/auth/login", {"email": ctx.get("email"), "password": "correct-horse-1"})
    tok = b.get("access_token") if isinstance(b, dict) else None
    st2, _, lst = h("GET", "/projects", token=tok)
    return st == 200 and st2 == 200 and any(isinstance(p, dict) and p.get("id") == ctx.get("project_id") for p in (lst or []))


ACCEPT = {"small": (accept_small, persist_small), "production": (accept_production, persist_production)}


# ---- start a build, test it, check quality --------------------------------------------------
def find_file(root: Path, name: str) -> Path | None:
    hits = [p for p in root.rglob(name) if not any(x in p.parts for x in ("node_modules", ".venv", ".git"))]
    return min(hits, key=lambda p: len(p.parts)) if hits else None


class App:
    def __init__(self, start_sh: Path, log: Path):
        self.start_sh, self.log, self.proc = start_sh, log, None

    def start(self, wait: int = 240) -> str | None:
        if port_open(PORT):
            return f"port {PORT} is already in use; stop whatever is running there and re-run"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        out = self.log.open("a")
        self.proc = subprocess.Popen(["bash", str(self.start_sh)], cwd=self.start_sh.parent, stdout=out,
                                     stderr=subprocess.STDOUT, start_new_session=True,
                                     env={**os.environ, "PORT": str(PORT)})
        t0 = time.time()
        while time.time() - t0 < wait:
            if port_open(PORT):
                time.sleep(1)
                return None
            if self.proc.poll() is not None:
                return f"start.sh exited with code {self.proc.returncode} (see {self.log})"
            time.sleep(1)
        self.stop()
        return f"nothing listening on port {PORT} after {wait}s (see {self.log})"

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            for sig, pause in ((signal.SIGTERM, 10), (signal.SIGKILL, 2)):
                try:
                    os.killpg(self.proc.pid, sig)
                except ProcessLookupError:
                    break
                t0 = time.time()
                while self.proc.poll() is None and time.time() - t0 < pause:
                    time.sleep(0.2)
        t0 = time.time()
        while port_open(PORT) and time.time() - t0 < 10:
            time.sleep(0.3)


def test_build(app_name: str, project: Path, log: Path) -> dict:
    out = {"project": str(project), "acceptance": 0, "acceptance_total": APPS[app_name]["checks"],
           "persists": None, "failed_checks": [], "start_error": None}
    start_sh = find_file(project, "start.sh")
    if not start_sh:
        out["start_error"] = "no start.sh in the project"
        return out
    accept, persist = ACCEPT[app_name]
    base = f"http://127.0.0.1:{PORT}"
    a = App(start_sh, log)
    err = a.start()
    if err:
        out["start_error"] = err
        return out
    try:
        res, ctx = accept(base)
    finally:
        a.stop()
    out["acceptance"] = sum(ok for _, ok in res)
    out["failed_checks"] = [n for n, ok in res if not ok]
    err = a.start()
    if err:
        out["persists"] = False
        out["restart_error"] = err
    else:
        try:
            out["persists"] = persist(base, ctx)
        finally:
            a.stop()
    return out


def quality(project: Path) -> dict:
    q = {}
    py = find_file(project, "pyproject.toml")
    if py and shutil.which("uv"):
        d = py.parent
        run(["uv", "sync", "-q"], cwd=d, timeout=900)
        src = "src" if (d / "src").is_dir() else "."
        _, t = run(["uv", "run", "pytest", "-q", "--cov", "--cov-report=term"], cwd=d, timeout=1800)
        m = re.search(r"(\d+) passed", t)
        f = re.search(r"(\d+) failed", t)
        cov = re.search(r"^TOTAL.*?(\d+(?:\.\d+)?)%\s*$", t, re.M)
        _, r = run(["uv", "run", "ruff", "check", "."], cwd=d, timeout=300)
        _, y = run(["uv", "run", "mypy", "--strict", src], cwd=d, timeout=900)
        num = lambda s: int(x.group(1)) if (x := re.search(r"Found (\d+) error", s)) else 0
        loc = 0
        for p in (d / src).rglob("*.py"):
            if not any(x in p.parts for x in (".venv", "tests", "migrations", "alembic")):
                loc += sum(1 for ln in p.read_text(errors="replace").splitlines() if ln.strip() and not ln.strip().startswith("#"))
        q.update(tests_passed=int(m.group(1)) if m else 0, tests_failed=int(f.group(1)) if f else 0,
                 coverage=f"{cov.group(1)}%" if cov else "n/a", ruff_errors=num(r), mypy_errors=num(y), lines=loc)
    pkg = find_file(project, "package.json")
    if pkg and shutil.which("npm"):
        d = pkg.parent
        run(["npm", "ci" if (d / "package-lock.json").exists() else "install", "--silent"], cwd=d, timeout=1200)
        scripts = json.loads(pkg.read_text()).get("scripts", {})
        status = lambda c: "✅" if c == 0 else "❌"
        q["web_build"] = status(run(["npm", "run", "-s", "build"], cwd=d, timeout=900)[0]) if "build" in scripts else "n/a"
        q["web_lint"] = status(run(["npm", "run", "-s", "lint"], cwd=d, timeout=600)[0]) if "lint" in scripts else "n/a"
        if "vitest" in pkg.read_text():
            q["web_tests"] = status(run(["npx", "vitest", "run"], cwd=d, timeout=900)[0])
        else:
            q["web_tests"] = status(run(["npm", "test", "--silent"], cwd=d, timeout=900)[0]) if "test" in scripts else "n/a"
    has = lambda *names: "✅" if any(find_file(project, n) for n in names) else "❌"
    q["files"] = {"README": has("README.md"), "Dockerfile": has("Dockerfile"),
                  "compose": has("docker-compose.yml", "compose.yml", "docker-compose.yaml"),
                  "CI": "✅" if any(project.rglob(".github/workflows/*.y*ml")) else "❌",
                  "migrations": has("alembic.ini"), ".env.example": has(".env.example")}
    return q


# ---- claude + plugin control ------------------------------------------------------------------
def plugin(enable: bool) -> None:
    code, out = run([CLAUDE, "plugin", "enable" if enable else "disable", PLUGIN], timeout=120)
    if code != 0 and "already" not in out.lower():
        say(f"  ! couldn't {'enable' if enable else 'disable'} the plugin: {out.strip()[:200]}")


def claude_p(prompt: str, cwd: Path, skip_permissions: bool) -> dict:
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json"] + (["--dangerously-skip-permissions"] if skip_permissions else [])
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    t0 = time.time()
    while p.poll() is None:
        print(f"\r  working… {int(time.time() - t0) // 60} min {int(time.time() - t0) % 60:02d} s", end="", flush=True)
        time.sleep(5)
    print()
    out = p.stdout.read() if p.stdout else ""
    try:
        return json.loads(out)
    except ValueError:
        return {"is_error": True, "result": (out + (p.stderr.read() if p.stderr else ""))[-500:]}


def claude_interactive(prompt: str, cwd: Path, skip_permissions: bool) -> int:
    cmd = [CLAUDE, prompt] + (["--dangerously-skip-permissions"] if skip_permissions else [])
    return subprocess.call(cmd, cwd=cwd)


MAX_UNATTENDED_SESSIONS = 12
MARKERS = ("MILESTONE DONE", "HANDOVER DONE", "STOPPED")


def answers_log(folder: Path) -> list[str]:
    path = folder / "answers.log"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def logged_answers(folder: Path) -> list[str]:
    return [ln for ln in answers_log(folder) if ln.strip() and not ln.startswith(MARKERS)]


def run_unattended(key: str, folder: Path, repo: str, start: datetime, budget: float | None,
                   skip_permissions: bool, state: dict) -> None:
    """D7: headless plugin sessions that answer their own cards from ANSWERS.md
    (skills/setup-project/references/unattended.md), resumed until the handover is done."""
    answers_file = f" Answers file: {folder / 'ANSWERS.md'}"  # same line: Windows cuts args at a newline
    prompt = PLUGIN_PROMPT.format(repo=repo) + answers_file
    stalled = 0
    for n in range(1, MAX_UNATTENDED_SESSIONS + 1):
        before = len(answers_log(folder))
        say(f"Plugin session {n}, headless…")
        result = claude_p(prompt, folder, skip_permissions)
        if result.get("is_error"):
            say(f"  ! the session ended with an error: {str(result.get('result'))[:300]}")
        lines = answers_log(folder)
        m = measure(log_dir_for(folder), sessions_in(log_dir_for(folder), start))
        say(f"  {len(lines) - before} new answer-log lines · cost so far ${m['cost_usd']:.2f}"
            + (f" of ${budget:.2f}" if budget else ""))
        if any(ln.startswith("HANDOVER DONE") for ln in lines):
            say("  Handover done.")
            return
        stop = next((ln for ln in lines if ln.startswith("STOPPED")), None)
        over = budget is not None and m["cost_usd"] > budget
        stalled = stalled + 1 if len(lines) == before else 0
        if stop or over or stalled >= 2:
            say(f"  Stopping: {stop or ('over budget' if over else 'two sessions in a row made no progress')}.")
            state.setdefault("runs", {}).setdefault(key, {})["stopped"] = True
            return
        prompt = RESUME_PROMPT.format(repo=repo) + answers_file
    say(f"  Stopping: {MAX_UNATTENDED_SESSIONS} sessions without a handover.")
    state.setdefault("runs", {}).setdefault(key, {})["stopped"] = True


# ---- commands --------------------------------------------------------------------------------
def cmd_check(_=None) -> bool:
    say("Checking tools")
    ok = True
    checks = [
        ("claude", [CLAUDE, "--version"], True), ("uv", ["uv", "--version"], True),
        ("git", ["git", "--version"], True), ("gh (signed in)", ["gh", "auth", "status"], True),
        ("node + npm (production app)", ["npm", "--version"], False), ("docker (optional)", ["docker", "--version"], False),
    ]
    say(f"  {'✅' if sys.version_info >= (3, 10) else '❌'} python {sys.version.split()[0]}")
    for name, cmd, required in checks:
        code, out = run(cmd, timeout=30)
        good = code == 0
        ok &= good or not required
        say(f"  {'✅' if good else ('❌' if required else '➖')} {name}{'' if good else ' (' + out.strip().splitlines()[0][:80] + ')' if out.strip() else ''}")
    code, out = run([CLAUDE, "plugin", "list"], timeout=60)
    installed = "dev-team-setup@" in out
    say(f"  {'✅' if installed else '❌'} plugin {PLUGIN} installed")
    if not installed and code == 0 and yes("  Install it now?"):
        run([CLAUDE, "plugin", "marketplace", "add", "AbrahamLinksus/dev-team-setup"], timeout=180)
        c, o = run([CLAUDE, "plugin", "install", PLUGIN], timeout=300)
        say("  " + (o.strip().splitlines()[-1] if o.strip() else f"exit {c}"))
        say("  Then in `claude` run: /plugin configure dev-team-setup@dev-team-setup  (your name + GitHub user)")
        installed = c == 0
    if not shutil.which("gh"):
        say("  Install gh: sudo pacman -S github-cli   (then: gh auth login)")
    return ok and installed


def cmd_clean(args) -> None:
    targets = [BENCH, HOME / "bench-baseline", HOME / "bench-plugin"]
    for a in APPS.values():
        targets += [PROJECTS / a["repo"], PROJECTS / f"{a['repo']}-wt"]
    targets = [t for t in targets if t.exists()]
    log_targets = [d for d in LOGS.glob("*") if re.search(r"-bench(-|$)|bench-baseline|bench-plugin", d.name)] if LOGS.exists() else []
    if not targets and not log_targets and not args.github:
        say("Nothing to clean.")
        return
    say("This deletes:")
    for t in targets:
        say(f"  {t}")
    for t in log_targets:
        say(f"  {t}  (Claude Code logs for that folder)")
    if args.github:
        owner = run(["gh", "api", "user", "-q", ".login"], timeout=30)[1].strip()
        repos = [f"{owner}/{a['repo']}" for a in APPS.values()
                 if run(["gh", "repo", "view", f"{owner}/{a['repo']}"], timeout=30)[0] == 0]
        for r in repos:
            say(f"  github.com/{r}  (needs: gh auth refresh -s delete_repo)")
    else:
        repos = []
    if not yes("Delete all of this?", default=False):
        say("Nothing deleted.")
        return
    for t in targets + log_targets:
        if t.is_dir() and not t.is_symlink():
            shutil.rmtree(t, ignore_errors=True)
        else:
            t.unlink(missing_ok=True)
    for r in repos:
        code, out = run(["gh", "repo", "delete", r, "--yes"], timeout=60)
        say(f"  {'deleted' if code == 0 else 'could not delete'} {r}{'' if code == 0 else ': ' + out.strip()[:150]}")
    say("Clean.")


def cmd_overhead(_=None) -> dict:
    say("Measuring plugin overhead (same tiny prompt, 3× without and 3× with the plugin)…")
    scratch = BENCH / "overhead"
    scratch.mkdir(parents=True, exist_ok=True)
    values = {}
    try:
        for mode in ("without", "with"):
            plugin(mode == "with")
            vals = []
            for i in range(3):
                code, out = run([CLAUDE, "-p", "Reply with just: ok", "--output-format", "json"], cwd=scratch, timeout=300)
                try:
                    u = json.loads(out).get("usage") or {}
                except ValueError:
                    say(f"  ! claude -p failed: {out.strip()[:200]}")
                    return {}
                ctx = sum(int(u.get(k) or 0) for k in FIELDS[:3])
                vals.append(ctx)
                say(f"  {mode} plugin · run {i + 1}: {ctx:,} input tokens")
            values[mode] = vals
    finally:
        plugin(True)
    res = {"without": int(statistics.median(values["without"])), "with": int(statistics.median(values["with"]))}
    res["overhead"] = res["with"] - res["without"]
    say(f"  → plugin adds {res['overhead']:,} tokens to every model call (median of 3).")
    state = load_state()
    state["overhead"] = res
    save_state(state)
    return res


def settings(state: dict) -> dict:
    s = state.setdefault("settings", {})
    if "skip_permissions" not in s:
        say("\nRuns can skip Claude Code's permission prompts, so you aren't asked to approve every command.")
        say("This only affects the benchmark sessions, which work inside ~/bench and ~/projects/bench-*.")
        s["skip_permissions"] = yes("Skip permission prompts in benchmark runs? (same for every run)", True)
        s["normal_unattended"] = yes("Run the normal sessions unattended (headless)? You won't need to watch them.", True) \
            if s["skip_permissions"] else False
    if "plugin_unattended" not in s:
        s["plugin_unattended"] = s["skip_permissions"] and yes(
            "Run the plugin sessions unattended too? The plugin answers its own cards from ANSWERS.md "
            "and logs each answer, so runs are repeatable.", True)
    if "budget_factor" not in s:
        s["budget_factor"] = float(ask("Stop a plugin run if it costs more than N × the normal run. N =", "10"))
    save_state(state)
    return s


def cmd_run(args) -> None:
    app, mode = args.app, args.mode
    key = f"{app}-{mode}"
    state = load_state()
    s = settings(state)
    folder = BENCH / key
    repo = APPS[app]["repo"]
    if folder.exists() and any(folder.iterdir()):
        if not yes(f"{folder} exists from an earlier run. Delete it and run {key} again?", default=False):
            return
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(APPS[app]["spec"])
    say(f"\n=== {key} ===")
    start = datetime.now(timezone.utc)

    if mode == "normal":
        plugin(False)
        if s["normal_unattended"]:
            say("Running a normal Claude Code session headless (plugin off). This can take a while…")
            result = claude_p(NORMAL_PROMPT, folder, s["skip_permissions"])
            if result.get("is_error"):
                say(f"  ! the session ended with an error: {str(result.get('result'))[:300]}")
        else:
            say("Opening a normal Claude Code session (plugin off). The prompt is already typed in.")
            say("Don't help it; if it stops early you may say 'continue until every item in Quality bar is met' (max 3).")
            say("When it's done: /exit")
            claude_interactive(NORMAL_PROMPT, folder, s["skip_permissions"])
        project = folder
    else:
        plugin(True)
        if (PROJECTS / repo).exists():
            if not yes(f"{PROJECTS / repo} exists from an earlier run. Delete it (and its worktrees)?", default=False):
                return
            shutil.rmtree(PROJECTS / repo, ignore_errors=True)
            shutil.rmtree(PROJECTS / f"{repo}-wt", ignore_errors=True)
        answers = ANSWERS.format(app=app, repo=repo)
        (folder / "ANSWERS.md").write_text(answers)
        normal_cost = (state.get("runs", {}).get(f"{app}-normal", {}).get("tokens") or {}).get("cost_usd") or 0
        budget = normal_cost * s["budget_factor"] if normal_cost else None
        say(answers)
        say(f"(Also saved to {folder / 'ANSWERS.md'}.)")
        if budget:
            say(f"Budget: ${budget:.2f} ({s['budget_factor']:g} × the normal run).")
        prompt = PLUGIN_PROMPT.format(repo=repo)
        sessions_done = 0
        if s.get("plugin_unattended"):
            run_unattended(key, folder, repo, start, budget, s["skip_permissions"], state)
        else:
            input("Press Enter to open the plugin session…")
        while not s.get("plugin_unattended"):
            say(f"(If the prompt doesn't appear in the session, paste it: {prompt})")
            claude_interactive(prompt, folder, s["skip_permissions"])
            sessions_done += 1
            m = measure(log_dir_for(folder), sessions_in(log_dir_for(folder), start))
            say(f"\nSession {sessions_done} ended · cost so far ${m['cost_usd']:.2f}"
                + (f" of ${budget:.2f} budget" if budget else ""))
            if budget and m["cost_usd"] > budget:
                say("  Over budget.")
            choice = ask("Next: [r]esume in a fresh session · [d]one (handover approved) · [s]top here (unfinished)", "r").lower()
            if choice.startswith("d"):
                break
            if choice.startswith("s"):
                state.setdefault("runs", {}).setdefault(key, {})["stopped"] = True
                break
            prompt = RESUME_PROMPT.format(repo=repo)
        project = next((p for p in (PROJECTS / repo, folder / repo) if p.exists()), folder)

    end = datetime.now(timezone.utc)
    say("Measuring tokens and cost…")
    tokens = measure(log_dir_for(folder), sessions_in(log_dir_for(folder), start))
    if mode == "plugin" and s.get("plugin_unattended"):
        # Unattended: the owner's interventions are the answers the plugin logged in their place.
        n = len(logged_answers(folder))
        tokens.update({"interventions": n, "answered_questions": n, "typed": 0})
    say(token_table(tokens, key))
    if not args.no_test:
        say(f"\nStarting the build from {project} and testing it…")
        tested = test_build(app, project, folder / "app.log")
        if tested["start_error"]:
            say(f"  ! couldn't start it: {tested['start_error']}")
        else:
            say(f"  acceptance {tested['acceptance']}/{tested['acceptance_total']} · survives restart: "
                f"{'✅' if tested['persists'] else '❌'}")
            for n in tested["failed_checks"]:
                say(f"    ❌ {n}")
        say("Checking code quality (tests, coverage, lint, types, web, files)…")
        q = quality(project)
    else:
        tested, q = {}, {}
    ui = None
    if app == "production" and not args.no_test and sys.stdin.isatty():
        say("\nOptional: start the web UI as the project's README says and try it (log in, create a project,")
        say("an issue, change its status, comment), on desktop and at 390 px wide in dev tools.")
        ui = ask("Did the UI work? [y]es / [p]artly / [n]o / [s]kip", "s")[:1]
    run_state = state.setdefault("runs", {}).setdefault(key, {})
    run_state.update({"start": start.isoformat(), "end": end.isoformat(), "folder": str(folder),
                      "project": str(project), "tokens": tokens, "test": tested, "quality": q, "ui": ui,
                      "step_minutes": step_times(project)})
    if run_state["step_minutes"]:
        say("Time per step (from taskgit's timing log):")
        say(times_table(run_state["step_minutes"]))
    if mode == "plugin":
        run_state["stopped"] = run_state.get("stopped", False)
    save_state(state)
    write_report(state)
    say(f"\nSaved. Results so far: {RESULTS}")


def step_times(project: Path) -> dict:
    """D10: minutes per step from taskgit's timing log (<git dir>/devteam-timing.log): each
    "<step> started" → "<step> done" pair, plus "waiting for you": the last event before an
    approve or reject (the card was out) → that answer."""
    log = project / ".git" / "devteam-timing.log"
    if not log.exists():
        return {}
    events = defaultdict(list)
    for line in log.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        ts = parse_ts(parts[0]) if len(parts) == 3 else None
        if ts:
            events[parts[1]].append((ts, parts[2]))
    out = defaultdict(lambda: {"minutes": 0.0, "count": 0})

    def add(label: str, a: datetime, b: datetime) -> None:
        out[label]["minutes"] += (b - a).total_seconds() / 60
        out[label]["count"] += 1

    for evs in events.values():
        evs.sort()
        open_steps: dict[str, datetime] = {}
        for i, (ts, ev) in enumerate(evs):
            m = re.match(r"(.+?) (started|done)$", ev)
            if m and m.group(2) == "started":
                open_steps[m.group(1)] = ts
            elif m and m.group(1) in open_steps:
                add(m.group(1), open_steps.pop(m.group(1)), ts)
            elif ev in ("approved", "rejected") and i:
                add("waiting for you (card → answer)", evs[i - 1][0], ts)
    return {k: {"minutes": round(v["minutes"], 1), "count": v["count"]} for k, v in out.items()}


def times_table(t: dict) -> str:
    if not t:
        return ""
    rows = ["| step | times | minutes |", "|---|---|---|"]
    rows += [f"| {k} | {v['count']} | {v['minutes']:.1f} |" for k, v in sorted(t.items(), key=lambda kv: -kv[1]["minutes"])]
    return "\n".join(rows)


def per_check(run_state: dict) -> str:
    """H7's headline: what one passed acceptance check cost."""
    passed = (run_state.get("test") or {}).get("acceptance")
    cost = (run_state.get("tokens") or {}).get("cost_usd")
    return f"${cost / passed:.2f}" if passed and cost else ""


def cell(v) -> str:
    return "" if v is None else str(v)


def write_report(state: dict) -> str:
    runs = state.get("runs", {})
    o = state.get("overhead")
    L = ["# Benchmark results", "", f"Updated {now_iso()}", ""]
    if o:
        L += ["## Overhead", "", "| Without plugin | With plugin | Added to every model call |", "|---|---|---|",
              f"| {o['without']:,} | {o['with']:,} | **{o['overhead']:,}** |", ""]
    for app in APPS:
        keys = [k for k in (f"{app}-normal", f"{app}-plugin") if k in runs]
        if not keys:
            continue
        L += [f"## {app.capitalize()} app", "",
              "| Run | Cost | All tokens | Output | Subagent tokens | Time | Sessions | Your interventions "
              "| Cost per passed check | Main session's share of cost |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for k in keys:
            t = runs[k].get("tokens", {})
            L.append(f"| {k}{' (stopped)' if runs[k].get('stopped') else ''} | ${t.get('cost_usd', 0):.2f} | "
                     f"{fmt(t.get('all_tokens', 0))} | {fmt(t.get('tokens', {}).get('output_tokens', 0))} | "
                     f"{fmt(t.get('subagent_tokens', 0))} | {t.get('minutes', 0):.0f} min | {len(t.get('sessions', []))} | "
                     f"{t.get('interventions', '')} | {per_check(runs[k])} | "
                     f"{pct((t.get('shares') or {}).get('main session', {}).get('cost_share', 0)) if t.get('shares') else ''} |")
        if len(keys) == 2:
            a, b = (runs[k].get("tokens", {}) for k in keys)
            if a.get("cost_usd") and a.get("all_tokens"):
                L.append(f"| **plugin ÷ normal** | **{b.get('cost_usd', 0) / a['cost_usd']:.1f}×** | "
                         f"{b.get('all_tokens', 0) / a['all_tokens']:.1f}× | | | | | | | |")
        L += ["", "| Run | Acceptance | Survives restart | Tests passed | Failed | Coverage | Ruff | Mypy | Lines |",
              "|---|---|---|---|---|---|---|---|---|"]
        for k in keys:
            t, q = runs[k].get("test", {}), runs[k].get("quality", {})
            acc = f"{t.get('acceptance', 0)}/{t.get('acceptance_total', APPS[app]['checks'])}" if t else ""
            if t.get("start_error"):
                acc += " (didn't start)"
            per = {True: "✅", False: "❌", None: ""}.get(t.get("persists"))
            L.append(f"| {k} | {acc} | {per} | {cell(q.get('tests_passed'))} | {cell(q.get('tests_failed'))} | "
                     f"{cell(q.get('coverage'))} | {cell(q.get('ruff_errors'))} | {cell(q.get('mypy_errors'))} | {cell(q.get('lines'))} |")
        if app == "production":
            L += ["", "| Run | Web build | Web lint | Web tests | README | Dockerfile | Compose | CI | Migrations | .env.example | UI |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
            for k in keys:
                q, f = runs[k].get("quality", {}), runs[k].get("quality", {}).get("files", {})
                ui = {"y": "✅", "p": "partly", "n": "❌"}.get(runs[k].get("ui") or "", "")
                L.append(f"| {k} | {cell(q.get('web_build'))} | {cell(q.get('web_lint'))} | {cell(q.get('web_tests'))} | "
                         + " | ".join(cell(f.get(x)) for x in ("README", "Dockerfile", "compose", "CI", "migrations", ".env.example"))
                         + f" | {ui} |")
        failed = [(k, runs[k].get("test", {}).get("failed_checks") or []) for k in keys]
        if any(f for _, f in failed):
            L += ["", "Failed acceptance checks:"]
            for k, f in failed:
                for n in f:
                    L.append(f"- {k}: {n}")
        for k in keys:
            if k.endswith("plugin") and runs[k].get("tokens"):
                L += ["", token_table(runs[k]["tokens"], k)]
        L.append("")
    text = "\n".join(L)
    BENCH.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(text)
    return text


def cmd_report(_=None) -> None:
    say(write_report(load_state()))


def cmd_tokens(args) -> None:
    log_dir = Path(args.project_dir) if args.project_dir else log_dir_for(Path.cwd())
    if not log_dir.is_dir():
        sys.exit(f"No session logs at {log_dir}. Run this from the folder you started claude in.")
    if args.session:
        sessions = args.session
    elif args.since:
        since = parse_ts(args.since)
        if since is None:
            sys.exit("--since must be an ISO time like 2026-11-09T10:00")
        sessions = sessions_in(log_dir, since)
    else:
        mains = sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        sessions = [mains[-1].stem] if mains else []
    if not sessions:
        sys.exit("No matching sessions.")
    m = measure(log_dir, sessions)
    print(json.dumps(m, indent=2) if args.json else token_table(m, args.label))


def cmd_all(_=None) -> None:
    say("bench.py: normal Claude Code vs /setup-project\n")
    if not cmd_check():
        say("\nFix the ❌ items above, then run: python3 bench.py all")
        return
    state = load_state()
    settings(state)
    if "overhead" not in state and yes("\nMeasure the plugin overhead first (~1 min)?"):
        cmd_overhead()
    for app in APPS:
        if app == "production" and not yes("\nRun the production benchmark too (long and more expensive)?"):
            break
        for mode in ("normal", "plugin"):
            key = f"{app}-{mode}"
            state = load_state()
            if key in state.get("runs", {}):
                say(f"\n{key}: already done (re-run it with: python3 bench.py run {app} {mode})")
                continue
            if not yes(f"\nStart {key}?"):
                say(f"Stopped before {key}. Run `python3 bench.py all` again to continue.")
                return
            cmd_run(argparse.Namespace(app=app, mode=mode, no_test=False))
    say("\n" + write_report(load_state()))
    say(f"\nDone. Results: {RESULTS}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("all").set_defaults(fn=cmd_all)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    c = sub.add_parser("clean")
    c.add_argument("--github", action="store_true", help="also delete the bench-* GitHub repos")
    c.set_defaults(fn=cmd_clean)
    sub.add_parser("overhead").set_defaults(fn=cmd_overhead)
    r = sub.add_parser("run")
    r.add_argument("app", choices=list(APPS))
    r.add_argument("mode", choices=["normal", "plugin"])
    r.add_argument("--no-test", action="store_true", help="skip starting and testing the build")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    t = sub.add_parser("tokens")
    t.add_argument("--project-dir")
    g = t.add_mutually_exclusive_group()
    g.add_argument("--session", nargs="+")
    g.add_argument("--since")
    g.add_argument("--latest", action="store_true")
    t.add_argument("--label", default="run")
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_tokens)
    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        return
    try:
        a.fn(a)
    except KeyboardInterrupt:
        say("\nInterrupted. Run the same command again to continue; finished runs are kept in ~/bench/state.json.")


if __name__ == "__main__":
    main()
