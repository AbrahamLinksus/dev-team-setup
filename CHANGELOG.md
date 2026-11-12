# Changelog

Every release raises `version` in `.claude-plugin/plugin.json`, and the top entry here must
match it (a test checks). Claude Code only offers an update when the version changes.

## 0.8.0

Right-sized builds that run in parallel, plain-language decisions, a spec critic, a production
gate and life after handover. Backlog M0–M7 (PRs #134–#141), merged through `backlog/v0.8`.

- **Right-sizing:**
  - project size from the spec's risk signals (backend, auth, database, multi-user, external
    services, AI/ML, deployment), not a guessed task count;
  - a task is one user-visible feature slice; one foundation task at most; caps of 8 / 15 / 30;
  - milestones only at risk checkpoints;
  - one commit per approved task (approve commits the TASKS/STATE/DECISIONS updates);
  - an LLD size cap, and an as-built sync that edits only what the milestone changed;
  - a stall watchdog (`taskgit.sh watch`) and a `stalled?` status row.
- **Task graph:**
  - `taskgraph.py`: waves, critical path, parallel factor, `--ready` scheduling and
    `--undeclared` files; every task declares Owner, Depends on and Files;
  - the graph on the planning card;
  - stages overlap, and next-milestone work runs while a milestone card waits;
  - `taskgit.sh catchup` merges main into open task branches after each approve;
  - `taskgit.sh changed` lists a task's paths for plan vs actual.
- **Plain language:**
  - "Do you write code?" at intake: builder or developer mode;
  - every decision card says what it means for you and what being wrong costs;
  - one "standard toolkit" card for forced tooling choices.
- **Spec critic:**
  - new `product-critic` agent: usage scenarios and gaps before the spec card;
  - a data-safety section the owner must answer;
  - scenarios become acceptance criteria and end-to-end tests.
- **Production gate:**
  - `templates/PRODUCTION.md` per project type;
  - gate items become criteria in the slices;
  - the handover can't be approved with an open item (build it or waive it).
- **Approve by using:**
  - "Try this" steps on every card;
  - an opt-in phone preview per milestone;
  - `capture.py flow` records short GIFs.
- **Cost and docs:**
  - cost by agent role on each task's Result line;
  - a rework flag on milestone cards;
  - `OWNER.md`, a one-screen page for the owner.
- **Handover hygiene:**
  - small minors are fixed, not listed;
  - `taskgit.sh lint` (executable bits, STATE.md leftovers, merged branches);
  - CI runs what the README claims.
- **After handover:** `/setup-project fix <bug>` (reproduce with a failing test first) and new
  features through the change-request flow with a fresh size.
- **Evals:** `cards-plain-language`, `critic-recipe-box`, `fix-routes-to-maintenance`.
- **CI:** the test jobs install Pillow (the GIF test).

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
