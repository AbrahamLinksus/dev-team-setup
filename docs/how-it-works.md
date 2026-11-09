# How it works

The detailed version: the pipeline, the agent team, the guardrails and the files each
project gets. For getting started, see the [README](../README.md).

## Flow

```
Idea → repo (you choose visibility)
→ Spec interview: rounds of questions until SPEC.md is complete, + wireframes for UI ⏸
→ HLD ⏸ → team picked from the HLD's modules ⏸ → LLD + conventions + packages ⏸
→ environment install ⏸ → task list ⏸
→ build loop, task by task: owner agent → tester → reviewer → debugger if needed → visual → result card ⏸
→ each milestone: architect syncs LLD to the code, docs updates README ⏸
→ handover: CI, ARCHITECTURE.md (as built), WALKTHROUGH.md, README run/test/extend ⏸
Anytime: a change request updates SPEC/HLD/LLD, shows a "what changes" card ⏸, re-plans tasks, resumes.
```

Every result comes with a visual (screenshot first, then chart/diagram, then table),
the task's goals vs what was achieved, and Approve / Request changes / Reject.
Approving a task squashes its branch into main and pushes it.

## How it stays safe

- **Checkpoints:** every agent step is committed and pushed to the task's own `wip/<id>`
  branch, so work survives a session ending mid-task (`/setup-project resume <repo>`).
- **Parallel tasks:** each task has its own worktree. Shared files (`TASKS.md`, `STATE.md`,
  `DECISIONS.md`) are only edited on main by the Orchestrator. Before a card is shown, the
  task is merged with current main and `scripts/check.sh` is re-run.
- **Enforced roles:** a PreToolUse hook (`hooks/scope_guard.py`) blocks each agent from
  writing outside its paths, running git write commands, or installing packages. After
  every step, a scope check reverts anything written some other way. Limits live in
  `skills/setup-project/scopes.json`; projects can override them in `.devteam/scopes.json`.
- **Conventions:** the Architect writes `docs/CONVENTIONS.md` (layering, SOLID, limits);
  `scripts/check.sh` enforces lint, strict types, complexity, layer rules and coverage;
  the Reviewer checks SOLID on the task's diff.

## Agents (26)

Generated from one spec: edit `tools/gen_agents.py`, then run `python3 tools/gen_agents.py`. Shared rules: `skills/setup-project/references/team-rules.md`.


| Pack | Agents |
|---|---|
| Core software | planner (Opus), researcher, architect (Opus), env-setup, backend-coder, frontend-coder, tester, reviewer (Opus, read-only), debugger (Opus), docs (Haiku), devops, git-pr (Haiku) |
| AI/ML | trainer, evaluator (Opus, LLM-as-judge), rag-engineer, prompt-engineer, agent-engineer (incl. MCP servers), mlops |
| Data science | data-acquisition (incl. scraping), data-cleaner (asks before dropping data, Pandera), eda (notebooks), statistician (Opus, causal inference), modeler (features + time series), explainer (Opus), visualizer, insights-reporter |

Unmarked agents use Sonnet.

## Usage

- `/setup-project build a RAG assistant over my lecture notes`
- `/setup-project resume <repo>` continues from the repo's `STATE.md` on any device

## Files created in each project

`STATE.md` (where things stand, for resuming), `TASKS.md`, `DECISIONS.md`,
`docs/SPEC.md` + `docs/wireframes/`, `docs/HLD.md`, `docs/LLD.md` (kept as-built),
`docs/CONVENTIONS.md`, and at handover `docs/ARCHITECTURE.md` + `docs/WALKTHROUGH.md`.
`.results/` holds images (git-ignored).

## Token use

1. **Section-based context.** The LLD is written in numbered, self-contained sections
   (`§2.1`…), kept stable at every as-built sync. Each task has a `Context:` line
   (`SPEC US-03 · LLD §2.1, §4 · files: src/auth/*`) listing exactly what its agents need.
2. **Briefs list exactly what to read.** Every brief has a `Read:` field built from a
   per-role default plus the task's `Context:`. Agents read nothing else; a missing piece is
   reported as a `Context gap` and added to the project's STATE.md "Context additions".
3. **Short reports, details in files.** Agents write full reports to
   `.results/<id>/<step>-<agent>.md` and return at most 12 lines. The Orchestrator never reads
   diffs, logs or test output itself; it passes file paths to the next agent.
4. **Fresh agents, fresh sessions.** Every step spawns a fresh agent, except rework on the
   same task (the owner agent or debugger is continued, at most twice). At each milestone and
   after a change request, the recommended option is to continue in a fresh chat with
   `/setup-project resume <repo>`, which rebuilds state from the repo's files.

## Setup

When you enable the plugin, it asks for:

| Option | What it does |
|---|---|
| `owner_name` | How the Orchestrator addresses you |
| `github_owner` | GitHub user/org for new project repos (visibility is asked every time) |
| `approval_mode` | `every-task` (default) or `batch-low-risk` (low-risk tasks approved together) |
| `cost_mode` | `quality` (default) or `balanced` (Sonnet reviewer/debugger on low-risk tasks, 2 debug rounds) |

Other notes:
- Visual capture uses Playwright + Chromium (`skills/setup-project/scripts/capture.py`).
  Mermaid is installed through npm the first time a diagram is rendered.
- GPU training runs on Colab/GCP; the trainer prepares the scripts for it.

## Development

```
python3 -m unittest discover -s tests -v   # structure, agents, scope guard (needs pyyaml)
bash tests/test_taskgit.sh                  # git scenarios against throwaway repos
python3 tools/gen_agents.py                 # regenerate agents/ after editing the spec
```

- `tests/test_taskgit.sh` has one scenario per git bug found so far (parallel approvals,
  change requests wiping recorded results, push failures, diverged main, stale worktrees…).
  Add a scenario before fixing the next one. `TASKGIT_UNDER_TEST=<path>` runs the suite
  against another copy of the script, e.g. to confirm a scenario fails on the old version.
- `tests/test_scope_guard.py` feeds the hook real JSON events, including known bypass
  attempts (chained commands, `bash -c`, `eval`, substitutions, newlines).
- CI (`.github/workflows/ci.yml`) runs both on every push and PR.
- `examples/todo-app/` shows real planning output from a dry run.
