# Changelog

Every release raises `version` in `.claude-plugin/plugin.json`, and the top entry here must
match it (a test checks). Claude Code only offers an update when the version changes.

## 0.6.0

Hardening release: 74 fixes from the problem list (PRs #1–#75), plus directory preparation.

- **Scope guard:** closes the known bypasses (inline code, wrappers, `find -exec`, git global
  options, `gh` writes, secrets in commands and reads, substitutions, background jobs); fails
  closed without Python 3.9+; pins each agent to its own task worktree; project overrides can
  only add restrictions.
- **taskgit:** checkpoints survive hooks and odd filenames, per-worktree dependency installs,
  stricter conflict and untracked-file checks, safer approve and reject.
- **capture.py:** `doctor [--install]` with a private venv, pinned Mermaid, timeouts, ANSI and
  font handling, container-safe Chromium.
- **Agents and skill:** shorter agent descriptions (about half the always-on tokens), absolute
  worktree paths in briefs, ports per task, pause and abandon, CLI card fallback.
- **Repo:** CI on Linux and macOS with Python 3.9 and 3.13, shellcheck, ruff, plugin
  validation; a regression test for every fixed hole; README requirements and disclosure of
  what the plugin runs and sends; `displayName` "Dev Team".

## 0.5.1

Last release before the problem-list fixes.
