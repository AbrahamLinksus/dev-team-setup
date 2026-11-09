# dev-team-setup

`/setup-project <problem>` puts together a team of subagents for a project, the way you'd
staff a dev team, then plans and builds it with you approving every step. Works from
your phone.

## Flow

```
Problem → Orchestrator (Opus) proposes a team → you approve
→ Planner: high-level design ⏸ → Researcher + Architect: low-level design + packages ⏸
→ Env-Setup (uv) ⏸ before installs → repo created (you choose visibility)
→ Planner: task list → build loop, task by task:
    owner agent → Tester → Reviewer → Debugger if needed → visual → result card ⏸
→ milestone card ⏸ → next milestone
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
`docs/HLD.md`, `docs/LLD.md`, `.results/` (images, git-ignored).

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
