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
Approving a task commits and pushes it.

## Agents (26)

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

- Repos are created under GitHub user `AbrahamLinksus`. You're asked about visibility every time.
- Visual capture uses Playwright + Chromium (`skills/setup-project/scripts/capture.py`).
  Mermaid is installed through npm the first time a diagram is rendered.
- GPU training runs on Colab/GCP; the trainer prepares the scripts for it.
