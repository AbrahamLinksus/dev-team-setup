#!/usr/bin/env python3
"""Scope guard for dev-team-setup agents.

Two modes, one source of truth (skills/setup-project/scopes.json + optional
<project>/.devteam/scopes.json overrides written by the Architect):

1. PreToolUse hook (default): reads the hook JSON from stdin. Acts only when the tool
   call comes from one of this plugin's agents (agent_type "dev-team-setup:<name>" or a
   bare <name> listed in scopes.json); everything else passes untouched.
   - Write/Edit/NotebookEdit: the target path must match the agent's `write` globs and
     not its `deny` globs.
   - Bash: checked against the agent's bash mode (none | readonly | code | full | git).
   Denials are returned as permissionDecision "deny" with a reason the agent can act on.

2. --check <agent> <root> <relpath...>: prints every path the agent was not allowed to
   change (used by `taskgit.sh scope` after each step, which catches writes made through
   Bash or scripts that the hook can't see).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from functools import lru_cache
from pathlib import Path

PLUGIN = "dev-team-setup"
ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = ROOT / "skills" / "setup-project" / "scopes.json"


@lru_cache(maxsize=None)
def _rx(glob: str) -> re.Pattern:
    i, out = 0, ""
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out += r"(?:.*/)?"; i += 3; continue
        if glob.startswith("**", i):
            out += r".*"; i += 2; continue
        out += {"*": r"[^/]*", "?": r"[^/]"}.get(c, re.escape(c)); i += 1
    return re.compile(rf"^{out}$")


def match(path: str, globs: list[str]) -> bool:
    return any(_rx(g).match(path) for g in globs)


def load_scopes(project_root: Path | None) -> dict:
    data = json.loads(DEFAULTS.read_text())
    if project_root:
        override = project_root / ".devteam" / "scopes.json"
        if override.is_file():
            try:
                for name, spec in json.loads(override.read_text()).get("agents", {}).items():
                    data["agents"].setdefault(name, {}).update(spec)
            except (OSError, ValueError):
                pass
    return data


def agent_name(agent_type: str | None, scopes: dict) -> str | None:
    if not agent_type:
        return None
    if ":" in agent_type:
        prefix, _, name = agent_type.rpartition(":")
        if prefix.split(":")[0] != PLUGIN:
            return None
    else:
        name = agent_type
    return name if name in scopes["agents"] else None


def find_root(path: Path) -> Path | None:
    for p in [path, *path.parents]:
        if (p / ".git").exists():
            return p
    return None


def expand(globs: list[str], scopes: dict) -> list[str]:
    out = []
    for g in globs:
        out += scopes.get("groups", {}).get(g[1:], []) if g.startswith("@") else [g]
    return out


def path_violation(name: str, rel: str, scopes: dict) -> str | None:
    """Return a reason if `name` may not write repo-relative path `rel`, else None."""
    spec = scopes["agents"][name]
    deny = expand(spec.get("deny", []), scopes) + expand(scopes.get("deny_all", []), scopes)
    allow = expand(spec.get("write", []), scopes)
    if match(rel, deny):
        return f"{name} may not change {rel} (owned by another role or by the Orchestrator)"
    if not match(rel, allow):
        shown = ", ".join(allow) if allow else "nothing (read-only role)"
        return f"{name} may only write: {shown}. Blocked: {rel}"
    return None


def abs_violation(name: str, file_path: str, cwd: str, scopes: dict) -> str | None:
    p = Path(file_path if os.path.isabs(file_path) else os.path.join(cwd or ".", file_path)).resolve()
    root = find_root(p.parent if not p.is_dir() else p)
    if root is not None:  # inside a project: the project's rules apply, even under /tmp
        return path_violation(name, p.relative_to(root).as_posix(), load_scopes(root))
    if match(str(p), scopes.get("scratch", [])):
        return None
    return f"{name} may only write inside the project worktree or scratch dirs ({', '.join(scopes.get('scratch', []))}). Blocked: {p}"


GIT_WRITE = re.compile(r"\bgit\b[^|;&]*\b(commit|push|reset|checkout|switch|restore|clean|rebase|merge|"
                       r"cherry-pick|revert|branch\s+-[dDmM]|worktree|stash|tag|rm|mv|am|apply)\b")
INSTALL = re.compile(r"\b(pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+(install|uninstall)\b|\buv\s+(add|remove|sync|lock)\b|"
                     r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|ci|update|up)\b|\bnpx\s+-y\b|"
                     r"\b(apt|apt-get|brew|conda|mamba)\s+install\b|\bcurl\b[^|]*\|\s*(ba)?sh\b")
DESTRUCTIVE = re.compile(r"(^|[;&|]\s*)\s*(sudo\s+)?(rm\s+-[a-zA-Z]*r[a-zA-Z]*f|rm\s+-[a-zA-Z]*f[a-zA-Z]*r)\s+(/|~|\$HOME)(\s|$)")
WRITE_CMDS = re.compile(r"(^|[;&|(]\s*)(rm|mv|cp|tee|touch|mkdir|rmdir|truncate|chmod|chown|ln|install|dd)\b|\bsed\s+(-[a-zA-Z]*i|--in-place)")
REDIRECT = re.compile(r"(?<![<>&0-9])(?:\d?>>?|&>)\s*([^\s;&|]+)")


def bash_violation(name: str, command: str, scopes: dict) -> str | None:
    mode = scopes["agents"][name].get("bash", "none")
    scratch = scopes.get("scratch", [])
    if mode == "none":
        return f"{name} has no shell access in this team. Use Read/Grep/Glob."
    if DESTRUCTIVE.search(command):
        return "destructive rm on a root/home path blocked"
    if mode == "git":
        allowed = re.fullmatch(r"\s*((bash\s+)?\S*taskgit\.sh\b.*|git\s+(status|log|diff|show|branch|remote|rev-parse|fetch)\b.*|python3\s+\S*capture\.py\b.*)\s*", command, re.S)
        return None if allowed else "git-pr may only run taskgit.sh, read-only git commands and capture.py"
    if GIT_WRITE.search(command):
        return "git history is managed by the Orchestrator (taskgit.sh) and git-pr; don't run git write commands"
    if mode != "full" and INSTALL.search(command):
        return "installing or removing packages is a Tier 1 decision: return DECISION NEEDED instead"
    if mode == "readonly":
        if WRITE_CMDS.search(command):
            return f"{name} is read-only: file-changing shell commands are blocked (write scratch files with Write under /tmp)"
        for target in REDIRECT.findall(command):
            t = target.strip("'\"")
            if t in ("/dev/null", "/dev/stderr", "/dev/stdout"):
                continue
            if not (match(t, scratch) or t.startswith(".results/") or "/.results/" in t):
                return f"{name} is read-only: redirecting output to {t} is blocked (use /tmp or .results/)"
    return None


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": f"[dev-team scope] {reason}"}}))
    sys.exit(0)


def hook_main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    scopes = load_scopes(None)
    name = agent_name(event.get("agent_type"), scopes)
    if not name:
        return  # not one of our agents: no opinion
    tool, inp, cwd = event.get("tool_name", ""), event.get("tool_input") or {}, event.get("cwd") or os.getcwd()
    reason = None
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        fp = inp.get("file_path") or inp.get("notebook_path")
        if fp:
            reason = abs_violation(name, fp, cwd, scopes)
    elif tool == "Bash":
        cmd = inp.get("command", "")
        root = find_root(Path(cwd).resolve())
        reason = bash_violation(name, cmd, load_scopes(root))
    if reason:
        deny(reason)


def check_main(argv: list[str]) -> None:
    name, root, paths = argv[0], Path(argv[1]).resolve(), argv[2:]
    scopes = load_scopes(root)
    if name not in scopes["agents"]:
        sys.exit(f"unknown agent: {name}")
    for rel in paths:
        if path_violation(name, rel.rstrip("/"), scopes):
            print(rel)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_main(sys.argv[2:])
    else:
        hook_main()
