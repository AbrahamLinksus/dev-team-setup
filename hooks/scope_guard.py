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
        try:
            if (p / ".git").exists():
                return p
        except OSError:  # unreadable directory: keep walking up
            continue
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
    try:
        is_dir = p.is_dir()
    except OSError:
        is_dir = False
    root = find_root(p if is_dir else p.parent)
    if root is not None:  # inside a project: the project's rules apply, even under /tmp
        return path_violation(name, p.relative_to(root).as_posix(), load_scopes(root))
    if match(str(p), scopes.get("scratch", [])):
        return None
    return f"{name} may only write inside the project worktree or scratch dirs ({', '.join(scopes.get('scratch', []))}). Blocked: {p}"


GIT_WRITE_SUBS = {"commit", "push", "reset", "checkout", "switch", "restore", "clean", "rebase", "merge",
                  "cherry-pick", "revert", "worktree", "stash", "tag", "rm", "mv", "am", "apply", "pull",
                  "update-ref", "filter-branch", "filter-repo", "gc", "prune", "init", "clone", "config"}
GIT_READ_SUBS = {"status", "log", "diff", "show", "rev-parse", "ls-remote", "ls-files", "fetch",
                 "shortlog", "blame", "describe", "rev-list", "cat-file"}
GIT_WRITE = re.compile(r"\bgit\b[^|;&\n]*?\s(" + "|".join(sorted(GIT_WRITE_SUBS, key=len, reverse=True)) +
                       r"|branch\s+-[dDmMcC]|remote\s+(add|remove|rm|set-url|rename))\b")
INSTALL = re.compile(r"\b(pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+(install|uninstall)\b|\buv\s+(add|remove|sync|lock)\b|"
                     r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|ci|update|up)\b|\bnpx\s+-y\b|"
                     r"\b(apt|apt-get|brew|conda|mamba)\s+install\b|\bcurl\b[^|]*\|\s*(ba)?sh\b")
DESTRUCTIVE = re.compile(r"(^|[;&|\n]\s*)\s*(sudo\s+)?(rm\s+-[a-zA-Z]*r[a-zA-Z]*f|rm\s+-[a-zA-Z]*f[a-zA-Z]*r)\s+(/|~|\$HOME)(\s|$)")
WRITE_CMDS = re.compile(r"(^|[;&|(\n]\s*)(rm|mv|cp|tee|touch|mkdir|rmdir|truncate|chmod|chown|ln|install|dd)\b|\bsed\s+(-[a-zA-Z]*i|--in-place)")
WRITE_NAMES = {"rm", "mv", "cp", "tee", "touch", "mkdir", "rmdir", "truncate", "chmod", "chown", "ln", "install",
               "dd", "shred", "unlink", "rsync"}
FIND_DELETE = re.compile(r"\bfind\b[^|;&\n]*\s-delete\b")
REDIRECT = re.compile(r"(?<![<>&0-9])(?:\d?>>?|&>)\s*([^\s;&|]+)")
SEPARATORS = {"&&", "||", ";", "|", "\n", ";;"}
WRAPPERS = {"sudo", "command", "exec", "env", "time", "nohup", "nice", "builtin", "timeout", "watch", "xargs",
            "parallel", "stdbuf", "ionice", "chronic", "unbuffer", "setsid", "flock", "doas", "caffeinate"}
# wrapper options that take a separate value (so the value isn't mistaken for the wrapped command)
WRAPPER_OPT_ARGS = {
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t"}, "doas": {"-u", "-C"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"}, "watch": {"-n", "--interval"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a", "--max-args", "--max-procs", "--delimiter",
              "--arg-file", "--replace", "--max-lines", "--eof", "--max-chars"},
    "parallel": {"-j", "--jobs", "-S", "--sshlogin", "-N", "--delay", "--timeout"},
    "stdbuf": {"-i", "-o", "-e"}, "ionice": {"-c", "-n", "-p"}, "flock": {"-w", "-E"},
}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
PIPE_FILTERS = {"head", "tail", "grep", "wc", "sort", "cut", "uniq", "cat", "less", "jq"}


def segments(command: str) -> list[list[str]] | None:
    """Split a shell command into simple commands, respecting quotes. None if unparseable
    or if it uses constructs we refuse to reason about (background &, subshell parens)."""
    lex = shlex.shlex(command.replace("2>&1", " "), posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return None
    segs, cur = [], []
    for t in tokens:
        if t in SEPARATORS:
            if cur:
                segs.append(cur)
            cur = []
        elif t in ("&", "(", ")", "<(", ">(") or set(t) <= set("();<>|&") and t not in (">", ">>", "<"):
            return None
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def strip_wrappers(tok: list[str]) -> list[str]:
    """`sudo -u x timeout -s 9 5 xargs -n1 git push` → `git push`."""
    i = 0
    while i < len(tok):
        name = os.path.basename(tok[i])
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok[i]):
            i += 1
            continue
        if name not in WRAPPERS:
            break
        i += 1
        takes = WRAPPER_OPT_ARGS.get(name, set())
        while i < len(tok) and (tok[i].startswith("-") or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok[i])):
            i += 2 if tok[i] in takes else 1
        if name in ("timeout", "flock") and i < len(tok):
            i += 1  # the duration / lock file
        if name == "watch" and i == len(tok) - 1 and " " in tok[i]:
            try:  # watch 'git push' runs its single argument through sh -c
                return strip_wrappers(shlex.split(tok[i]))
            except ValueError:
                return tok[i:]
    return tok[i:]


def find_exec_cmds(tok: list[str]) -> list[str]:
    """`find . -exec git commit -m x {} ;` → ["git commit -m x {}"]."""
    if not tok or os.path.basename(tok[0]) != "find":
        return []
    out, i = [], 0
    while i < len(tok):
        if tok[i] in FIND_EXEC:
            j = i + 1
            while j < len(tok) and tok[j] not in (";", "+"):
                j += 1
            if j > i + 1:
                out.append(shlex.join(tok[i + 1:j]))
            i = j
        i += 1
    return out


def git_sub(tok: list[str]) -> tuple[str, list[str]]:
    """For a `git ...` token list, skip global options (-C dir, -c k=v, --git-dir=…) and
    return (subcommand, rest)."""
    i = 1
    while i < len(tok) and tok[i].startswith("-"):
        i += 2 if tok[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    return (tok[i], tok[i + 1:]) if i < len(tok) else ("", [])


def capture_cmds(tok: list[str]) -> list[str]:
    """The shell commands `capture.py term --cmd "<cmd>"` would run (it uses shell=True)."""
    idx = next((i for i, t in enumerate(tok) if os.path.basename(t) == "capture.py"), None)
    if idx is None:
        return []
    out, args = [], tok[idx + 1:]
    for i, a in enumerate(args):
        if a in ("--cmd", "--cm") and i + 1 < len(args):
            out.append(args[i + 1])
        elif a.startswith(("--cmd=", "--cm=")):
            out.append(a.split("=", 1)[1])
    return out


def inner_commands(tok: list[str]) -> list[str]:
    """Commands hidden inside bash -c / sh -c / eval / capture.py --cmd."""
    if not tok:
        return []
    if tok[0] in ("bash", "sh", "zsh", "dash") and "-c" in tok:
        i = tok.index("-c")
        return tok[i + 1:i + 2]
    if tok[0] == "eval":
        return [" ".join(tok[1:])]
    return capture_cmds(tok) + find_exec_cmds(tok)


def embedded_commands(command: str) -> list[str]:
    """Every command nested one level inside `command` (bash -c, eval, capture.py --cmd)."""
    return [c for seg in segments(command) or [] for c in inner_commands(strip_wrappers(seg))]


RUNNERS = {("uv", "run"), ("poetry", "run"), ("pipenv", "run"), ("pdm", "run"), ("conda", "run")}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
# interpreter -> its flags that take code inline
INLINE_FLAGS = {"node": {"-e", "--eval", "-p", "--print"}, "deno": {"eval"}, "bun": {"-e", "--eval"},
                "ruby": {"-e"}, "php": {"-r"}}
INLINE_TEXT = re.compile(r"\b(python[0-9.]*|pypy3?)\s+(-\S+\s+)*-[a-zA-Z]*c|\b(node|bun)\s+(-\S+\s+)*(-e|-p|--eval|--print)\b|"
                         r"\bperl\s+(-\S+\s+)*-[a-zA-Z]*[eE]|\bruby\s+(-\S+\s+)*-e\b|\bphp\s+-r\b|\b(ba|z|da|k)?sh\s+[^-\s]")


def strip_runner(tok: list[str]) -> list[str]:
    """`uv run [opts] python …` → `python …`."""
    if len(tok) >= 2 and (os.path.basename(tok[0]), tok[1]) in RUNNERS:
        i = 2
        while i < len(tok) and tok[i].startswith("-"):
            i += 2 if tok[i] in ("--with", "--python", "-p", "--project", "--directory", "-n", "--name") else 1
        return tok[i:]
    return tok


def inline_code(command: str) -> str | None:
    """Code run from the command line (python -c, node -e, perl -e, bash script.sh …), which no
    text rule can inspect. Returns the offending command, or None."""
    segs = segments(command)
    if segs is None or "$(" in command or "`" in command:
        m = INLINE_TEXT.search(command)
        return m.group(0) if m else None
    for seg in segs:
        tok = strip_runner(strip_wrappers(seg))
        if not tok:
            continue
        name, args = os.path.basename(tok[0]), tok[1:]
        opts = []
        for a in args:  # options before the script/first argument
            if not a.startswith("-") and not (name == "deno" and a == "eval"):
                break
            opts.append(a)
        if re.fullmatch(r"python[0-9.]*|pypy3?", name) and any(not o.startswith("--") and "c" in o[1:] for o in opts):
            return " ".join(tok)[:80]
        if name == "perl" and any(not o.startswith("--") and set(o[1:]) & {"e", "E"} for o in opts):
            return " ".join(tok)[:80]
        if name in INLINE_FLAGS and (set(opts) & INLINE_FLAGS[name] or (name == "deno" and args[:1] == ["eval"])):
            return " ".join(tok)[:80]
        if name in SHELLS and "-c" not in args and len(args) > len(opts):
            return " ".join(tok)[:80]  # runs a script file the guard can't see into
        if name in ("source", "."):
            return " ".join(tok)[:80]
    return None


def git_write_in(command: str, depth: int = 0) -> bool:
    segs = segments(command)
    if segs is None or "$(" in command or "`" in command:
        # can't reason about structure (subshells, substitutions): fall back to a text scan
        return bool(GIT_WRITE.search(command))
    for seg in segs:
        tok = strip_wrappers(seg)
        if tok and os.path.basename(tok[0]) == "git":
            sub, rest = git_sub(tok)
            if sub in GIT_WRITE_SUBS or (sub == "branch" and any(a.startswith("-") and set(a[1:]) & set("dDmMcC") for a in rest)):
                return True
        if depth < 3 and any(git_write_in(c, depth + 1) for c in inner_commands(tok)):
            return True
    return False


def git_mode_violation(command: str, depth: int = 0) -> str | None:
    """git-pr: every simple command must be on the allowlist."""
    if "$(" in command or "`" in command:
        return "git-pr may not use command substitution ($(...) or backticks)"
    segs = segments(command)
    if segs is None:
        return "git-pr commands must be plain commands joined by && ; || or | (no subshells, background jobs or unbalanced quotes)"
    prev_pipe_ok = False
    for seg in segs:
        tok = seg
        if any(t in (">", ">>", "<") for t in tok):
            return "git-pr may not redirect output to files"
        name = os.path.basename(tok[0]) if tok else ""
        ok = False
        if name == "cd" and len(tok) <= 2:
            ok = True
        elif name == "taskgit.sh" or (name in ("bash", "sh") and len(tok) > 1 and os.path.basename(tok[1]) == "taskgit.sh"):
            ok = True
        elif name in ("python3", "python") and len(tok) > 1 and os.path.basename(tok[1]) == "capture.py":
            # capture.py term --cmd runs its argument through a shell: it must pass the same allowlist
            for inner in capture_cmds(tok):
                why = git_mode_violation(inner, depth + 1) if depth < 3 else "nested too deep"
                if why:
                    return f"capture.py --cmd would run a blocked command: {why}"
            ok = True
        elif name == "git":
            sub, rest = git_sub(tok)
            if sub in GIT_READ_SUBS:
                ok = True
            elif sub == "branch" and all(a in ("--list", "-a", "-v", "-vv", "-r", "--show-current", "--all") for a in rest):
                ok = True
            elif sub == "remote" and all(a in ("-v",) for a in rest):
                ok = True
        elif name in PIPE_FILTERS:
            ok = True
        if not ok:
            return f"git-pr may only run taskgit.sh, read-only git commands and capture.py. Blocked: {' '.join(tok)[:80]}"
    return None


def bash_violation(name: str, command: str, scopes: dict, depth: int = 0) -> str | None:
    mode = scopes["agents"][name].get("bash", "none")
    scratch = scopes.get("scratch", [])
    if mode == "none":
        return f"{name} has no shell access in this team. Use Read/Grep/Glob."
    if DESTRUCTIVE.search(command):
        return "destructive rm on a root/home path blocked"
    if mode == "git":
        return git_mode_violation(command)
    # commands nested in bash -c / eval / capture.py --cmd get the same checks as top-level ones
    for inner in embedded_commands(command):
        why = bash_violation(name, inner, scopes, depth + 1) if depth < 3 else "commands nested too deep"
        if why:
            return f"nested command blocked: {why}"
    if git_write_in(command):
        return "git history is managed by the Orchestrator (taskgit.sh) and git-pr; don't run git write commands"
    if mode != "full" and INSTALL.search(command):
        return "installing or removing packages is a Tier 1 decision: return DECISION NEEDED instead"
    if mode == "readonly":
        inline = inline_code(command)
        if inline:
            return (f"{name} is read-only: inline code (python -c, node -e, perl -e, bash script.sh …) can't be "
                    f"checked, so it's blocked. Write the script to /tmp with Write and run that file instead. "
                    f"Blocked: {inline}")
        hidden = [strip_wrappers(seg) for seg in segments(command) or []]
        if WRITE_CMDS.search(command) or FIND_DELETE.search(command) or any(
                tok and os.path.basename(tok[0]) in WRITE_NAMES for tok in hidden):
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
    try:
        reason = evaluate(name, event, scopes)
    except Exception as exc:  # fail closed for our agents: a crashing hook would let the call through
        reason = f"scope guard could not evaluate this call ({type(exc).__name__}: {exc}); blocked to be safe"
    if reason:
        deny(reason)


def evaluate(name: str, event: dict, scopes: dict) -> str | None:
    tool, inp, cwd = event.get("tool_name", ""), event.get("tool_input") or {}, event.get("cwd") or os.getcwd()
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        fp = inp.get("file_path") or inp.get("notebook_path")
        if not isinstance(fp, str) or not fp:
            raise ValueError("missing or non-string file path")
        return abs_violation(name, fp, cwd, scopes)
    if tool == "Bash":
        cmd = inp.get("command", "")
        if not isinstance(cmd, str):
            raise ValueError("non-string command")
        return bash_violation(name, cmd, load_scopes(find_root(Path(cwd).resolve())))
    return None


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
