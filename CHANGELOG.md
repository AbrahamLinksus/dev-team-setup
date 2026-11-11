# Changelog

Every release raises `version` in `.claude-plugin/plugin.json`, and the top entry here must
match it (a test checks). Claude Code only offers an update when the version changes.

## 0.7.0

Faster runs, visible costs and guardrails, and a working benchmark. PRs #80–#115.

- **Faster:**
  - `approval_mode: autopilot` approves low-risk tasks with every goal met on its own and sends the card afterwards with one-tap **Undo** (`taskgit.sh undo`);
  - `cost_mode: fast` (Sonnet for every role except planner and architect; Opus still reviews high-risk tasks);
  - up to 3 independent tasks start at the same time;
  - tester and reviewer run in parallel;
  - work continues while a card waits;
  - `check.sh` isn't re-run on a tree that already passed;
  - dependency installs use the shared caches;
  - a quick track for small ideas;
  - a fresh session every 6 tasks.
- **Cheaper:**
  - SKILL.md split into a core plus stage files read on demand (about 6.7k → 2.7k tokens when the skill loads);
  - stable-first agent briefs;
  - full reports only when someone will read them;
  - CI keeps the always-on context under 2,000 tokens (now ~1,600).
- **Visible:**
  - cost on every result card, and a `budget_usd` cap that pauses the run;
  - status rows for the team's agents in the agent panel;
  - the guard's blocks shown on cards;
  - agent ID cards;
  - a progress line, glossary and "why we're asking" on cards;
  - a one-screen summary on resume;
  - `docs/guardrails.md`.
- **Easier to start:**
  - try it locally with no GitHub account;
  - a three-line opener;
  - the skill stops with one line where it can't run agents (claude.ai chat).
- **Benchmark (bench.py):**
  - unattended plugin runs;
  - tokens by agent and step with cost shares;
  - minutes per step;
  - cost per passed check.
  - Fixed: a headless deadlock, the plugin left disabled after a plain run, a Windows encoding crash, a signed-out CLI recorded as a 0/8 run, and no budget cap on subscription plans (now capped on price-weighted tokens), plus Windows process handling.
- **Repo:**
  - disclosure of what the plugin runs and sends;
  - `displayName`, icon, privacy page and listing URLs;
  - strict validation, a Windows CI job and a plugin eval suite.

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
