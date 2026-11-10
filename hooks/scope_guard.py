#!/usr/bin/env python3
"""Scope guard for dev-team-setup agents.

Two modes, one source of truth (skills/setup-project/scopes.json + optional
<project>/.devteam/scopes.json overrides written by the Architect):

1. PreToolUse hook (default): reads the hook JSON from stdin. Acts only when the tool
   call comes from one of this plugin's agents (agent_type "dev-team-setup:<name>" with <name>
   listed in scopes.json); everything else passes untouched. A bare "<name>" is NOT ours: users
   and other plugins have agents called reviewer, tester, docs …, and `claude --agent tester`
   sets agent_type on the main thread too.
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
    prefix, sep, name = agent_type.rpartition(":")
    if not sep or prefix.split(":")[0] != PLUGIN:
        return None  # bare names belong to the user or other plugins
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


# S13: .env, .env.local, .env.production, .envrc … hold secrets; only .env.example is documentation
SECRET_FILE = re.compile(r"(^|/)\.env(\.[^/]+)?$|(^|/)\.envrc$")


def is_secret_file(path: str) -> bool:
    p = path.replace("\\", "/")
    return bool(SECRET_FILE.search(p)) and not p.endswith(".env.example")


def secret_in_command(command: str) -> str | None:
    """A shell command that names a secret file (cat .env, cp .env.local x, source .envrc …).
    `--env-file .env` is fine: it loads the values into a process without printing them."""
    for seg in segments(command) or []:
        for i, t in enumerate(seg):
            if t.startswith("--env-file=") or (i and seg[i - 1] == "--env-file"):
                continue
            if is_secret_file(t.strip("'\"")):
                return t
    if segments(command) is None:
        m = re.search(r"\S*\.env(rc|\.[A-Za-z0-9_-]+)?\b", command)
        if m and is_secret_file(m.group(0)) and "--env-file" not in command:
            return m.group(0)
    return None


def path_violation(name: str, rel: str, scopes: dict) -> str | None:
    """Return a reason if `name` may not write repo-relative path `rel`, else None."""
    if is_secret_file(rel):
        return f"{name} may not write {rel}: it holds secrets (document keys in .env.example instead)"
    spec = scopes["agents"][name]
    deny = expand(spec.get("deny", []), scopes) + expand(scopes.get("deny_all", []), scopes)
    allow = expand(spec.get("write", []), scopes)
    if match(rel, deny):
        return f"{name} may not change {rel} (owned by another role or by the Orchestrator)"
    if not match(rel, allow):
        shown = ", ".join(allow) if allow else "nothing (read-only role)"
        return f"{name} may only write: {shown}. Blocked: {rel}"
    return None


def is_task_worktree(root: Path) -> bool:
    """Agents work in linked worktrees at <repo>-wt/<id> (taskgit.sh start), never in a main checkout,
    whose .git is a directory rather than a file."""
    return (root / ".git").is_file() and root.parent.name.endswith("-wt")


def abs_violation(name: str, file_path: str, cwd: str, scopes: dict) -> str | None:
    p = Path(file_path if os.path.isabs(file_path) else os.path.join(cwd or ".", file_path)).resolve()
    try:
        is_dir = p.is_dir()
    except OSError:
        is_dir = False
    root = find_root(p if is_dir else p.parent)
    if root is not None:  # inside a project: the project's rules apply, even under /tmp
        if not is_task_worktree(root):
            return (f"{name} may only write inside its task's worktree (<repo>-wt/<id>, the Worktree: path in its "
                    f"brief); {root} is not one (the main checkout?). Blocked: {p}")
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
                     r"\b(apt|apt-get|brew|conda|mamba)\s+install\b|\bcurl\b[^|]*\|\s*(ba)?sh\b|"
                     r"\bcapture\.py\s+doctor\b[^|;&\n]*--install\b|"  # the plugin's own deps: Orchestrator only
                     # S9: other package managers and one-shot runners that download packages
                     r"\bpoetry\s+(add|remove|install|update|lock)\b|\bpipx\s+(install|run|inject|upgrade)\b|"
                     r"\bpip3?\s+download\b|\bcargo\s+(add|install|remove)\b|\bgo\s+(get|install)\b|"
                     r"\b(pnpm|yarn)\s+dlx\b|\bbunx\b|\bnpm\s+(exec|x)\b|\buvx\b|\buv\s+tool\s+(install|run)\b|"
                     r"\buv\s+run\b[^|;&\n]*\s--with(-requirements)?\b|\bmake\s+install\b|\bgem\s+install\b|"
                     r"\bcomposer\s+(require|install|update)\b|\bmicromamba\s+install\b|\bdotnet\s+add\s+package\b|"
                     r"\b(curl|wget)\b[^|;&\n]*\|\s*(sudo\s+)?(ba|z|da)?sh\b|"
                     r"\b(curl|wget)\b[^|;&\n]*\|\s*(sudo\s+)?python[0-9.]*\b")
NPX_FETCH_FLAGS = {"-y", "--yes", "-p", "--package"}


def npx_fetch(command: str, cwd: str | None) -> str | None:
    """`npx <bin>` runs a local binary when node_modules/.bin has it, and otherwise downloads the
    package. Returns the offending command when it would download, else None."""
    here = cwd or os.getcwd()
    for seg in segments(command) or []:
        tok = strip_wrappers(seg)
        if not tok:
            continue
        if os.path.basename(tok[0]) == "cd" and len(tok) == 2:
            here = tok[1] if os.path.isabs(tok[1]) else os.path.join(here, tok[1])
            continue
        if os.path.basename(tok[0]) != "npx":
            continue
        args = tok[1:]
        if set(args) & NPX_FETCH_FLAGS or any(a.startswith("--package=") for a in args):
            return " ".join(tok)[:80]
        name = next((a for a in args if not a.startswith("-")), "")
        name = name.split("@")[0] if not name.startswith("@") else "@" + name[1:].split("@")[0]
        binary = name.rsplit("/", 1)[-1]
        found = any((Path(d) / "node_modules" / ".bin" / b).exists()
                    for d in [here, *map(str, Path(here).parents)] for b in (binary, binary + ".cmd"))
        if name and not found:
            return " ".join(tok)[:80]
    return None
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


SCRIPTS = ROOT / "skills" / "setup-project" / "scripts"
# git options that run a program or write a file, even on read-only subcommands
GIT_GLOBAL_UNSAFE = re.compile(r"^(-c.*|--config-env.*|--exec-path.*)$")
GIT_ARG_UNSAFE = re.compile(r"^(--output|--upload-pack|--receive-pack|--exec|--ext-diff|--textconv|-O|--open-files-in-pager)(=.*)?$")


def is_plugin_script(arg: str, name: str, cwd: str | None) -> bool:
    """True only for this plugin's own copy of `name` (not a look-alike such as /tmp/evil/taskgit.sh)."""
    if os.path.basename(arg) != name:
        return False
    p = Path(arg) if os.path.isabs(arg) else Path(cwd or os.getcwd()) / arg
    try:
        return os.path.normcase(str(p.resolve())) == os.path.normcase(str((SCRIPTS / name).resolve()))
    except OSError:
        return False


def git_mode_violation(command: str, depth: int = 0, cwd: str | None = None) -> str | None:
    """git-pr: every simple command must be on the allowlist."""
    if "$(" in command or "`" in command:
        return "git-pr may not use command substitution ($(...) or backticks)"
    segs = segments(command)
    if segs is None:
        return "git-pr commands must be plain commands joined by && ; || or | (no subshells, background jobs or unbalanced quotes)"
    for seg in segs:
        tok = seg
        if any(t in (">", ">>", "<") for t in tok):
            return "git-pr may not redirect output to files"
        name = os.path.basename(tok[0]) if tok else ""
        ok = False
        if name == "cd" and len(tok) <= 2:
            if len(tok) == 2:  # later relative script paths resolve from here
                cwd = tok[1] if os.path.isabs(tok[1]) else os.path.join(cwd or os.getcwd(), tok[1])
            ok = True
        elif is_plugin_script(tok[0], "taskgit.sh", cwd) or (
                name in ("bash", "sh") and len(tok) > 1 and is_plugin_script(tok[1], "taskgit.sh", cwd)):
            ok = True
        elif name in ("python3", "python") and len(tok) > 1 and is_plugin_script(tok[1], "capture.py", cwd):
            if INSTALL.search(shlex.join(tok)):
                return "git-pr may not install the capture dependencies (capture.py doctor --install is the Orchestrator's)"
            # capture.py term --cmd runs its argument through a shell: it must pass the same allowlist
            for inner in capture_cmds(tok):
                why = git_mode_violation(inner, depth + 1, cwd) if depth < 3 else "nested too deep"
                if why:
                    return f"capture.py --cmd would run a blocked command: {why}"
            ok = True
        elif name in ("taskgit.sh", "capture.py") or (len(tok) > 1 and os.path.basename(tok[1]) in ("taskgit.sh", "capture.py")):
            return f"git-pr may only run the plugin's own scripts in {SCRIPTS}. Blocked: {' '.join(tok)[:80]}"
        elif name == "git":
            sub, rest = git_sub(tok)
            gopts = tok[1:len(tok) - len(rest) - 1]
            bad = [a for a in gopts if GIT_GLOBAL_UNSAFE.match(a)] + [a for a in rest if GIT_ARG_UNSAFE.match(a)]
            if sub in ("fetch", "ls-remote") and "-u" in rest:
                bad.append("-u")
            if bad:
                return f"git-pr may not use git options that run programs or write files ({', '.join(bad)})"
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


GH_READ = {("pr", v) for v in ("view", "list", "status", "diff", "checks")} | \
          {("issue", v) for v in ("view", "list", "status")} | \
          {("repo", v) for v in ("view", "list")} | {("release", v) for v in ("view", "list")} | \
          {("run", v) for v in ("view", "list", "watch")} | {("workflow", v) for v in ("view", "list")} | \
          {("auth", "status"), ("search", "*"), ("status", "*"), ("--version", "*"), ("version", "*")}
GH_GLOBAL_ARGS = {"-R", "--repo", "--hostname"}
GH_API_WRITE = {"-f", "-F", "--field", "--raw-field", "--input"}


def gh_write(command: str) -> str | None:
    """Any gh command that isn't on the read-only allowlist (S11): repo edit/delete, pr merge,
    secret set, api -X POST … Returns the offending command, else None."""
    segs = segments(command)
    if segs is None:
        m = re.search(r"\bgh\s+\S+", command)
        return m.group(0) if m else None
    for seg in segs:
        tok = strip_wrappers(seg)
        if not tok or os.path.basename(tok[0]) != "gh":
            continue
        words, i = [], 1
        while i < len(tok) and len(words) < 2:
            if tok[i] in GH_GLOBAL_ARGS:
                i += 2
                continue
            if not tok[i].startswith("-") or not words:
                words.append(tok[i])
            i += 1
        group, verb = (words + ["", ""])[:2]
        if (group, verb) in GH_READ or (group, "*") in GH_READ:
            continue
        if group == "api":
            method = next((tok[j + 1] for j, a in enumerate(tok[:-1]) if a in ("-X", "--method")), "GET")
            if method.upper() == "GET" and not set(tok) & GH_API_WRITE and not any(
                    a.startswith(("--method=", "-X", "--field=", "--raw-field=")) and a not in ("-X",) for a in tok):
                continue
        return " ".join(tok)[:80]
    return None


def destructive(command: str, cwd: str | None, scratch: list[str]) -> str | None:
    """Recursive deletes outside the current worktree (whatever the flag spelling: -rf, -r -f,
    --recursive --force, -R), and `kill … -1` (every process the user owns)."""
    here = cwd or os.getcwd()
    for seg in segments(command) or []:
        tok = strip_wrappers(seg)
        if not tok:
            continue
        name = os.path.basename(tok[0])
        if name == "cd" and len(tok) == 2:
            here = tok[1] if os.path.isabs(tok[1]) else os.path.join(here, tok[1])
            continue
        if name in ("kill", "pkill") and "-1" in tok[2:]:
            return "kill -1 would signal every process you own: blocked"
        if name != "rm":
            continue
        opts = [a for a in tok[1:] if a.startswith("-") and a != "--"]
        if not any(a == "--recursive" or (not a.startswith("--") and set(a[1:]) & {"r", "R"}) for a in opts):
            continue
        root = find_root(Path(here).resolve())
        for arg in (a for a in tok[1:] if not a.startswith("-")):
            if arg.startswith(("~", "$")):
                return f"recursive delete of {arg} (outside the worktree) blocked"
            p = Path(arg if os.path.isabs(arg) else os.path.join(here, arg)).resolve()
            if match(p.as_posix(), scratch):
                continue
            if root is None or p == root or root not in p.parents:
                return f"recursive delete outside the worktree blocked: {arg} → {p}"
    return None


def bash_violation(name: str, command: str, scopes: dict, depth: int = 0, cwd: str | None = None) -> str | None:
    mode = scopes["agents"][name].get("bash", "none")
    scratch = scopes.get("scratch", [])
    if mode == "none":
        return f"{name} has no shell access in this team. Use Read/Grep/Glob."
    if DESTRUCTIVE.search(command):
        return "destructive rm on a root/home path blocked"
    why = destructive(command, cwd, scratch)
    if why:
        return why
    if mode != "git" and unbounded_background(command):
        return UNBOUNDED_BACKGROUND
    if mode == "git":
        return git_mode_violation(command, cwd=cwd)
    # commands nested in bash -c / eval / capture.py --cmd get the same checks as top-level ones
    for inner in embedded_commands(command):
        why = bash_violation(name, inner, scopes, depth + 1, cwd) if depth < 3 else "commands nested too deep"
        if why:
            return f"nested command blocked: {why}"
    if git_write_in(command):
        return "git history is managed by the Orchestrator (taskgit.sh) and git-pr; don't run git write commands"
    gh = gh_write(command)
    if gh:
        return f"GitHub changes (repos, PRs, issues, releases, secrets…) belong to the Orchestrator; only read-only gh commands are allowed. Blocked: {gh}"
    if mode != "full" and npx_fetch(command, cwd):
        return (f"npx would download a package that isn't in node_modules ({npx_fetch(command, cwd)}): "
                "installing packages is a Tier 1 decision, return DECISION NEEDED instead")
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
    if tool in ("Read", "Grep"):
        fp = inp.get("file_path") or inp.get("path") or ""
        if isinstance(fp, str) and is_secret_file(fp):
            return f"{name} may not read {fp}: it holds secrets. Key names are documented in .env.example."
        return None
    if tool == "Bash" and isinstance(inp.get("command"), str):
        secret = secret_in_command(inp["command"])
        if secret:
            return (f"{name} may not read or change {secret}: it holds secrets. Use .env.example for key names, "
                    f"or load the values into a process with --env-file.")
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        fp = inp.get("file_path") or inp.get("notebook_path")
        if not isinstance(fp, str) or not fp:
            raise ValueError("missing or non-string file path")
        return abs_violation(name, fp, cwd, scopes)
    if tool == "Bash":
        cmd = inp.get("command", "")
        if not isinstance(cmd, str):
            raise ValueError("non-string command")
        scopes = load_scopes(find_root(Path(cwd).resolve()))
        why = bash_violation(name, cmd, scopes, cwd=cwd)
        if why is None and inp.get("run_in_background") and scopes["agents"][name].get("bash", "none") != "none" \
                and not starts_with_timeout(cmd):
            why = UNBOUNDED_BACKGROUND
        return why
    return None


UNBOUNDED_BACKGROUND = ("background processes must end on their own so nothing outlives your step: start them "
                        "with `timeout <seconds>` (e.g. `timeout 120 uvicorn app:app &`), stop them when done, "
                        "and don't use nohup/setsid/disown")


def starts_with_timeout(command: str) -> bool:
    try:
        tok = shlex.split(command)
    except ValueError:
        return False
    tok = [t for t in tok if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t)]
    return bool(tok) and os.path.basename(tok[0]) == "timeout"


def unbounded_background(command: str) -> bool:
    """S12: `uvicorn app:app &` keeps running after the agent finishes. A backgrounded command must
    start with `timeout N`; detaching tools (nohup, setsid, disown) are never allowed."""
    lex = shlex.shlex(command.replace("2>&1", " "), posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace, lex.whitespace_split = " \t\r", True
    try:
        tokens = list(lex)
    except ValueError:
        return "&" in command
    cur: list[str] = []
    for t in tokens + [";"]:
        if t in SEPARATORS or t == "&":
            words = [w for w in cur if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", w)]
            if words and os.path.basename(words[0]) in ("nohup", "setsid", "disown"):
                return True
            if t == "&" and words and os.path.basename(words[0]) != "timeout":
                return True
            cur = []
        elif t not in ("(", ")"):
            cur.append(t)
    return False


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
