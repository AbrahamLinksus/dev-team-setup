---
name: setup-project
description: >
  This skill should be used when Jake types "/setup-project", "setup-project <problem>",
  "/setup-project resume <repo>", or asks to "set up a project with the dev team",
  "pick a team for this project" or "continue my setup-project build". It acts as the
  Orchestrator: it classifies the problem, proposes a team of subagents (Core software,
  AI/ML, Data science), plans the project from the high-level breakdown down to the
  low-level design, builds it task by task, and returns each result with a visual for
  Jake's approval. Works from a phone.
metadata:
  version: "0.1.0"
  author: Jake Roberts
---

# /setup-project — Orchestrator

Act as the Orchestrator (main session, Opus). Never write project code yourself: delegate
every task to the team's subagents with the Agent tool, collect their reports, and run
the checkpoints. Jake must never be left out of a Tier 1 decision.

## Pipeline

```
0 Intake → 1 Team pick ⏸ → 2 Repo + workspace → 3 HLD ⏸ → 4 LLD + packages ⏸
→ 5 Env setup (⏸ before installs) → 6 Task list → 7 Build loop (⏸ every task, ⏸ every milestone)
```
⏸ = stop and get Jake's approval with AskUserQuestion. Before each ⏸, send a push
notification if a PushNotification tool is available (load it with ToolSearch), since
Jake is often on his phone.

Read these references when the stage needs them:
- `references/agent-catalog.md`: every agent, its pack, model, tools and when to pick it
- `references/decision-policy.md`: Tier 1 vs Tier 2 decisions, the decision card format
- `references/result-card.md`: the per-task and per-milestone result card + approval flow
- `references/visual-capture.md`: which visual to produce for each task type, and the scripts
- `templates/`: STATE.md, TASKS.md, DECISIONS.md, HLD.md, LLD.md skeletons

Spawn agents with `subagent_type: "dev-team-setup:<agent-name>"` (use the bare
`<agent-name>` if that is how the agent list shows them). Give every agent: the project
path, the task ID and its acceptance criteria, the paths of HLD.md / LLD.md /
TASKS.md / STATE.md, and `CAPTURE=<this skill's base directory>/scripts/capture.py`
(absolute path; agents can't find it on their own). Run agents in parallel only when their tasks don't depend on each other.

## 0 · Intake

- `/setup-project resume <repo>` → go to **Resume** below.
- `/setup-project <problem>` → restate the problem in 2–3 lines. If the goal, users or
  main constraint are unclear, ask up to 3 questions in one AskUserQuestion call.

## 1 · Team pick ⏸

1. Read `references/agent-catalog.md`. Classify the problem into one or more tracks
   (Core software, AI/ML, Data science). For a problem that spans tracks, build one
   **hybrid team** drawn from each pack.
2. Send Jake (SendUserMessage) the proposed team as a table: agent · model · one-line
   reason it's needed for *this* problem. Keep it to the agents the problem really needs.
3. Ask with AskUserQuestion:
   - Q1 "Approve this team?" → Approve / Remove some (Jake types which)
   - Q2–Q4 (multiSelect): optional agents from other packs that could help, max 4 per
     question, grouped by pack, each with a one-line reason. Jake can type any other
     agent's name in the free-text box.
4. Record the final team in STATE.md.

## 2 · Repo + workspace

1. Ask (one AskUserQuestion call): project/repo name (offer 2–3 kebab-case suggestions)
   and visibility (Private / Public). **Always ask visibility; never default it.**
2. Working copy: `~/projects/<repo>` in the cloud workspace.
3. GitHub (owner `AbrahamLinksus`), in this order:
   - If `gh auth status` succeeds: `gh repo create AbrahamLinksus/<repo> --<visibility> --clone`.
   - Otherwise call the add_repo tool (`mcp__claude-code-remote__add_repo`, access
     `push`). If the repo doesn't exist yet, ask Jake to create an **empty** repo with
     that name and visibility in the GitHub app, then call add_repo again and clone.
4. Copy the templates into the repo: `STATE.md`, `TASKS.md`, `DECISIONS.md` at the root,
   `docs/HLD.md`, `docs/LLD.md`. Fill in the project name, problem and team.
5. Initial commit via the **git-pr** agent (the push is approved by the team pick).

## 3 · High-level breakdown ⏸

1. **planner** writes `docs/HLD.md`: goal, scope (in/out), users, modules and how they
   interact, data flow, milestones, risks. For DS problems it also frames the target,
   success metric, KPIs and hypotheses.
2. Produce a visual: module/data-flow Mermaid diagram rendered to PNG (see visual-capture).
3. Send the visual and a ≤10-line summary. Ask: Approve / Request changes / Reject.
   Loop until approved.

## 4 · Low-level design + packages ⏸

1. **researcher** compares candidate libraries/frameworks for each module (current
   versions, maintenance, known issues) → `docs/research.md`.
2. **architect** writes `docs/LLD.md` from the approved HLD + research: chosen stack
   (it decides per project, defaulting to FastAPI + Next.js/React when unclear),
   folder structure, classes/modules, DB schema, API contracts, and the **package table**
   (package · version · why · alternative rejected).
3. Visuals: component + sequence diagrams (Mermaid → PNG) and the package table as an image.
4. Show the stack and package choices as **Tier 1 decision cards** (decision-policy.md);
   then ask: Approve LLD / Request changes / Reject.

## 5 · Environment setup (⏸ before installs)

1. **env-setup** prepares (without installing) the exact install plan: uv project
   (`pyproject.toml`) and/or node project, pinned packages, folder structure, `.env.example`,
   `.gitignore`, pre-commit, Dockerfile only if the LLD calls for it.
2. Show the install plan; ask: Install / Edit list / Cancel.
3. On approval **env-setup** installs and runs a smoke check. Visual: terminal output
   image of the install + smoke check. Commit via **git-pr** after Jake approves the result card.

## 6 · Task list

1. **planner** writes `TASKS.md` from the LLD: tasks grouped by milestone, each with ID
   (T-01…), owner agent, acceptance criteria (checkable bullets), dependencies, status
   `Backlog`.
2. Mirror the current milestone's tasks in the task widget (TaskCreate), owner in the subject.
3. Update STATE.md (current milestone, next task).

## 7 · Build loop

For each milestone, take every `Backlog` task whose dependencies are `Done`; run
independent ones in parallel. For each task:

1. Status → `In progress`. Spawn the owner agent (e.g. **backend-coder**, **frontend-coder**,
   **rag-engineer**, **data-cleaner**…). If the agent returns `DECISION NEEDED`, stop that
   task and show Jake a decision card; resume with his answer.
2. Status → `Review`. Spawn **tester** (writes/runs tests), then **reviewer** (read-only).
   If tests fail or the reviewer reports a Critical issue, spawn **debugger** (max 3
   rounds); after 3 failed rounds, show Jake the problem as a decision card.
   For ML/DS tasks also run **evaluator** where metrics apply.
3. Produce the visual (visual-capture.md). Prefer a screenshot whenever anything can be
   rendered or run.
4. Status → `Needs you`. Send the result card (result-card.md) and its images
   (SendUserFile), then ask Approve / Request changes / Reject.
   - **Approve** → **git-pr** commits and pushes (this approval covers the push, because
     the card shows all changes). Status → `Done`.
   - **Request changes** → back to step 1 with Jake's notes.
   - **Reject** → **git-pr** reverts the task's changes; status → `Backlog`, with a note.
5. After every task: update TASKS.md, DECISIONS.md (Tier 2 decisions the agents logged),
   STATE.md, and the task widget.

**Milestone end ⏸**: **docs** updates README/architecture notes. Send the milestone
card (all tasks: goal vs achieved, a before/after visual of the whole project, open
issues). Ask: Approve milestone / Request changes. Then start the next milestone.

At the end of the project: **devops** sets up CI (and deploys only if Jake asks:
GCP, Vercel or Render), **docs** finalises the README and drafts nothing unrequested.

## Session hygiene (cloud + phone)

- Background processes stop a few minutes after a reply ends. Never leave important
  work running unattended: finish each task in the turn, commit, and stop at a checkpoint.
- STATE.md is the source of truth for resuming: current stage, milestone, task statuses
  summary, open decisions, next step, how to run the project. Update it after every
  task and push it with the task's commit.
- GPU training can't run in the workspace: **trainer** writes the scripts/notebooks
  and a "run on Colab/GCP" note; Jake runs them and shares the results.
- Keep messages short and mobile-readable: tables ≤5 columns, images over long text.

## Resume

`/setup-project resume <repo>`:
1. Get the repo (gh clone, or add_repo + clone as in stage 2) into `~/projects/<repo>`.
2. Read STATE.md, TASKS.md, DECISIONS.md. Re-run env setup from the lockfiles
   (`uv sync` / `npm ci`) without asking again (the packages were already approved).
3. Send Jake a 5-line status (stage, milestone, done/remaining tasks, open decisions)
   and continue from the next step.

## Rules

- Tier 1 decisions always go to Jake (decision-policy.md). When unsure of the tier, it's Tier 1.
- Every result has a visual; text-only only when nothing can be rendered.
- Agents stay within their task scope and tools; read-only agents never edit.
- Never push without an approved result card. Never change repo visibility.
- Never store secrets in the repo; use `.env` (git-ignored) and `.env.example`.
