---
name: setup-project
description: >
  This skill should be used when Jake types "/setup-project", "setup-project <problem>",
  "/setup-project resume <repo>", or asks to "set up a project with the dev team",
  "pick a team for this project", "continue my setup-project build" or says "continue"
  after a setup-project session was interrupted. It acts as the Orchestrator: it
  classifies the problem, proposes a team of subagents (Core software, AI/ML, Data science),
  plans the project from the high-level breakdown down to the low-level design and coding
  conventions, builds it task by task with checkpoints that survive the session ending, and
  returns each result with a visual for Jake's approval. Works from a phone.
metadata:
  version: "0.2.0"
  author: Jake Roberts
---

# /setup-project — Orchestrator

Act as the Orchestrator (main session, Opus). Never write project code yourself: delegate
every task to the team's subagents with the Agent tool, collect their reports, run the
checkpoints, and run the approval gates. Jake must never be left out of a Tier 1 decision.

## Pipeline

```
0 Intake → 1 Team pick ⏸ → 2 Repo + workspace → 3 HLD ⏸ → 4 LLD + conventions + packages ⏸
→ 5 Env setup (⏸ before installs) → 6 Task list → 7 Build loop (⏸ every task, ⏸ every milestone)
```
⏸ = stop and get Jake's approval with AskUserQuestion. Before each ⏸, send a push
notification if a PushNotification tool is available (load it with ToolSearch), since
Jake is often on his phone.

Paths used below (`<skill>` = this skill's base directory, shown when the skill loads):
- `CAPTURE=<skill>/scripts/capture.py`: screenshots, terminal images, diagrams, tables
- `TASKGIT=<skill>/scripts/taskgit.sh`: wip branches, worktrees, checkpoints, approve/reject
- `<skill>/templates/`: STATE, TASKS, DECISIONS, HLD, LLD, CONVENTIONS skeletons

References (read when the stage needs them):
- `references/agent-catalog.md`: every agent, its pack, model, tools and when to pick it
- `references/decision-policy.md`: Tier 1 vs Tier 2, the decision card format
- `references/result-card.md`: per-task and per-milestone result card + approval flow
- `references/visual-capture.md`: which visual for each task type
- `references/checkpointing.md`: checkpoint protocol, TASK_PROGRESS.md format, resume algorithm

Spawn agents with `subagent_type: "dev-team-setup:<agent-name>"` (or the bare
`<agent-name>` if that is how the agent list shows them). Every brief contains: the
worktree path to work in, the task ID and its acceptance criteria verbatim, the paths of
STATE.md / TASKS.md / docs/HLD.md / docs/LLD.md / docs/CONVENTIONS.md, and the absolute
`CAPTURE` and `TASKGIT` paths (agents can't find them on their own). Run agents in
parallel only for tasks that don't depend on each other; each task has its own worktree.

## 0 · Intake

- `/setup-project resume <repo>`, or "continue" after an interruption → **Resume** below.
- `/setup-project <problem>` → restate the problem in 2–3 lines. If the goal, users or
  main constraint are unclear, ask up to 3 questions in one AskUserQuestion call.

## 1 · Team pick ⏸

1. Read `references/agent-catalog.md`. Classify the problem into tracks (Core software,
   AI/ML, Data science); for a problem that spans tracks, build one **hybrid team**.
2. Send Jake (SendUserMessage) the proposed team: agent · model · one-line reason for *this* problem.
3. AskUserQuestion: Q1 "Approve this team?" (Approve / Remove some); Q2–Q4 (multiSelect)
   optional agents from other packs, max 4 per question, each with a one-line reason.
   Jake can type any other agent's name in the free-text box.

## 2 · Repo + workspace

1. One AskUserQuestion call: repo name (2–3 kebab-case suggestions) and visibility
   (Private / Public). **Always ask visibility; never default it.**
2. GitHub (owner `AbrahamLinksus`), in order:
   - `gh auth status` works → `gh repo create AbrahamLinksus/<repo> --<visibility>`.
   - Otherwise call add_repo (`mcp__claude-code-remote__add_repo`, access `push`). If the
     repo doesn't exist, ask Jake to create an **empty** repo with that name and
     visibility in the GitHub app, then call add_repo again.
3. Clone to `~/projects/<repo>` (main checkout; only `approve` changes main).
4. Copy templates: `STATE.md`, `TASKS.md`, `DECISIONS.md` at the root;
   `docs/HLD.md`, `docs/LLD.md`, `docs/CONVENTIONS.md`. Fill in project, problem, team.
   Add `.gitignore` with `.env`, `.results/`, `.venv/`, `node_modules/`.
5. Commit and push this skeleton to main (covered by the team-pick approval).
6. Planning stages 3–5 run on `wip/plan`: `$TASKGIT start ~/projects/<repo> plan`.

## 3 · High-level breakdown ⏸

1. **planner** writes `docs/HLD.md` in the plan worktree (goal, scope in/out, users,
   modules, data flow, milestones, risks; for DS work also target, metric, KPIs, hypotheses).
   Checkpoint: `$TASKGIT checkpoint <repo> plan "HLD drafted"`.
2. Render the data-flow diagram (`$CAPTURE mermaid`). Send it and a ≤10-line summary.
3. Ask Approve / Request changes / Reject; loop until approved. Record the approval in
   `TASK_PROGRESS.md` of the plan worktree and checkpoint.

## 4 · Low-level design + conventions + packages ⏸

1. **researcher** → `docs/research.md` (2–4 candidates per decision point, with sources). Checkpoint.
2. **architect** → `docs/LLD.md` (stack, folders, modules/classes, schema, API contracts,
   sequences, pinned package table incl. dev tooling) and `docs/CONVENTIONS.md` (layering,
   SOLID rules for this project, limits, automated checks, layer contracts). Checkpoint.
3. Visuals: component/sequence diagrams, the package table and the layer map as images.
4. Every stack/package choice → one Tier 1 decision card (decision-policy.md). Then ask:
   Approve LLD + conventions / Request changes / Reject.

## 5 · Environment setup (⏸ before installs)

1. **env-setup** phase 1 returns the install plan (no installs). Show it; ask Install / Edit / Cancel.
2. Phase 2 on approval: installs, writes `scripts/check.sh` + tool configs + pre-commit,
   runs a smoke check and `scripts/check.sh`. Visual: terminal images.
3. Checkpoint, then send the planning result card (HLD + LLD + env). On approval:
   **git-pr** runs `$TASKGIT approve <repo> plan "chore: project plan, design and environment"`.

## 6 · Task list

1. **planner** writes `TASKS.md` from the LLD (tasks per milestone; ID, owner, deps,
   status `Backlog`, 2–5 checkable acceptance criteria). Commit to main with the plan
   approval if still open, otherwise as `chore: task list` (covered by the LLD approval).
2. Mirror the current milestone in the task widget (TaskCreate); update STATE.md.

## 7 · Build loop

For each milestone, take every `Backlog` task whose dependencies are `Done`; run
independent ones in parallel. For each task follow `references/checkpointing.md`:

1. `wt=$($TASKGIT start <repo> T-07)`. Write `TASK_PROGRESS.md` (steps pending), checkpoint.
2. Owner agent (e.g. **backend-coder**, **frontend-coder**, **rag-engineer**…) works in `$wt`.
   `DECISION NEEDED` → record it in TASK_PROGRESS.md, checkpoint, ask Jake, resume with
   the answer. Done → mark the step ✅, checkpoint.
3. **tester** (runs `scripts/check.sh`: lint, types, complexity, layers, tests + coverage)
   → checkpoint → **reviewer** (read-only, SOLID checklist) → checkpoint. Failing checks
   or a Critical/Major review → **debugger** or the owner agent (max 3 rounds; record the
   round in TASK_PROGRESS.md); after 3 rounds, show Jake a decision card.
   For ML/DS tasks also run **evaluator** where metrics apply.
4. Produce the visual (visual-capture.md); screenshots first.
5. Send the result card (result-card.md, including the Conventions line; get the changes
   with `$TASKGIT diffstat <repo> T-07`) and ask Approve / Request changes / Reject.
   - **Approve** → update TASKS.md (Done + result), DECISIONS.md, STATE.md inside `$wt`,
     then **git-pr** runs `$TASKGIT approve`. The approval covers the push to main.
   - **Request changes** → back to step 2 with Jake's notes (same branch).
   - **Reject** → **git-pr** runs `$TASKGIT reject`; status Backlog with Jake's reason.

**Milestone end ⏸**: **docs** updates README/architecture notes on a `wip/M<n>-docs`
task branch. Send the milestone card; ask Approve milestone / Request changes.

Project end: **devops** sets up CI (deploys only if Jake asks: GCP, Vercel or Render).

## Checkpoint rule (usage can run out at any moment)

- Checkpoint (`$TASKGIT checkpoint`) after **every** agent step and **before** spawning
  the next agent, so at most one step is ever lost. Pushing `wip/*` branches is
  pre-approved by Jake; **main changes only via `approve`**.
- `TASK_PROGRESS.md` (on the wip branch) holds the step states, debugger round and any open
  decision. It is removed automatically when the task is squashed into main.
- Never leave servers or background jobs running at the end of a turn.

## Resume

Run this for `/setup-project resume <repo>` or "continue" (details in checkpointing.md):
1. Get the repo into `~/projects/<repo>` (reuse it if present; else gh clone or add_repo + clone).
2. Read STATE.md, TASKS.md, DECISIONS.md on main; run `$TASKGIT list <repo>` for open wip branches.
3. For each wip branch: `$TASKGIT start` (restores the worktree), read TASK_PROGRESS.md,
   re-sync deps (`uv sync` / `npm ci`, no approval needed, they're already approved),
   re-run `scripts/check.sh` once to confirm ✅ steps still hold, then restart the first
   step not marked ✅. An open decision is asked again.
4. Send Jake: "Resumed <repo> at T-07 · reviewer step (coder ✅, tester ✅)", then continue.

## Rules

- Tier 1 decisions always go to Jake (decision-policy.md). When unsure of the tier, it's Tier 1.
- Every result has a visual; text-only only when nothing can be rendered.
- Agents stay within their task scope, worktree and tools; read-only agents never edit.
- main changes only through `$TASKGIT approve` after an approved card. Never force-push,
  never change repo visibility, never commit secrets.
- GPU training can't run in the workspace: **trainer** prepares Colab/GCP scripts.
- Keep messages mobile-readable: tables ≤5 columns, images over long text.
