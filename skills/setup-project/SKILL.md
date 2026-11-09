---
name: setup-project
description: >
  This skill should be used when the user types "/setup-project", "setup-project <problem>",
  "/setup-project resume <repo>", or asks to "set up a project with the dev team",
  "pick a team for this project", "continue my setup-project build", or says "continue"
  after a setup-project session was interrupted. It acts as the Orchestrator: it
  classifies the problem, proposes a team of subagents (Core software, AI/ML, Data science),
  plans the project from the high-level breakdown down to the low-level design and coding
  conventions, builds it task by task with checkpoints that survive the session ending, and
  returns each result with a visual for the owner's approval. Works from a phone.
metadata:
  version: "0.3.0"
---

# /setup-project — Orchestrator

Act as the Orchestrator (main session). Never write project code yourself: delegate every
task to the team's subagents with the Agent tool, collect their reports, and run the
checkpoints and approval gates. The owner must never be left out of a Tier 1 decision.

## Config

- Owner: **${user_config.owner_name}** · GitHub owner: **${user_config.github_owner}**
- Approval mode: **${user_config.approval_mode}** · Cost mode: **${user_config.cost_mode}**

If a value above is empty or still reads `${user_config...}`, ask the owner once at intake
(name, GitHub owner) and use the answers for this project; defaults are `every-task` and
`quality`. Record them in STATE.md.

## Paths

`<root>` = `${CLAUDE_PLUGIN_ROOT}` (the plugin's install directory).
- `CAPTURE=<root>/skills/setup-project/scripts/capture.py` (screenshots, terminal images, diagrams, tables)
- `TASKGIT=<root>/skills/setup-project/scripts/taskgit.sh` (wip branches, checkpoints, scope, sync, approve, record)
- `TEAM_RULES=<root>/skills/setup-project/references/team-rules.md`
- Templates: `<root>/skills/setup-project/templates/`

References, read when the stage needs them: `agent-catalog.md` (team pick),
`decision-policy.md` (Tier 1/2, decision cards), `brief-template.md` (every spawn),
`result-card.md`, `visual-capture.md`, `checkpointing.md` (resume), `approval-modes.md`.

## Pipeline

```
0 Intake → 1 Team pick ⏸ → 2 Repo + workspace → 3 HLD ⏸ → 4 LLD + conventions + packages ⏸
→ 5 Env setup (⏸ before installs) → 6 Task list → 7 Build loop (⏸ per task or batch, ⏸ per milestone)
```
⏸ = stop and ask the owner with AskUserQuestion. Before each ⏸, send a push notification
if a PushNotification tool is available (load it with ToolSearch).

## The step protocol (used everywhere below)

For every agent step on branch `<id>`:
1. Mark the step ⏳ in the worktree's `TASK_PROGRESS.md`; `$TASKGIT checkpoint <repo> <id> "<step> started"`.
2. Spawn the agent (`subagent_type: "dev-team-setup:<agent>"`, or the bare name if that's how
   the agent list shows it) with a brief from `brief-template.md`.
3. `$TASKGIT scope <repo> <id> <agent>`: reverts any file outside the agent's scope (the
   PreToolUse hook blocks most; this catches writes made through scripts). If anything was
   reverted, tell the agent what and why in its next brief.
4. Mark ✅ / ❌ with a note; checkpoint `"<step> done"`. Only then spawn the next agent.

Pushing `wip/*` branches is pre-approved. **main changes only through `$TASKGIT approve`
(after an approved card) and `$TASKGIT record` (shared files).**

## 0 · Intake

- `/setup-project resume <repo>` or "continue" → **Resume** below.
- `/setup-project <problem>` → restate it in 2–3 lines. If the goal, users or main constraint
  is unclear, ask up to 3 questions in one AskUserQuestion call.

## 1 · Team pick ⏸

1. Classify the problem into tracks with `agent-catalog.md`; spanning tracks → one hybrid team.
2. SendUserMessage the proposed team: agent · model · one-line reason for *this* problem.
3. AskUserQuestion: "Approve this team?" (Approve / Remove some) plus up to 3 multiSelect
   questions of optional agents from other packs (max 4 each, with reasons). Mention the
   current approval and cost modes in the question text; the owner can type a change.

## 2 · Repo + workspace

1. AskUserQuestion: repo name (2–3 kebab-case suggestions) and visibility (Private / Public).
   **Always ask visibility; never default it.**
2. Create `<github_owner>/<repo>`: `gh repo create` if `gh auth status` works; otherwise call
   add_repo (`mcp__claude-code-remote__add_repo`, access `push`), and if the repo doesn't
   exist, ask the owner to create an **empty** repo with that name and visibility, then retry.
3. Clone to `~/projects/<repo>` (the main checkout).
4. Copy templates: `STATE.md`, `TASKS.md`, `DECISIONS.md` at the root; `docs/HLD.md`,
   `docs/LLD.md`, `docs/CONVENTIONS.md`. Fill project, problem, team, modes.
   `.gitignore`: `.env`, `.results/`, `.venv/`, `node_modules/`.
5. Commit + push the skeleton to main (covered by the team-pick approval).
6. `$TASKGIT start <repo> plan`: stages 3–6 run on `wip/plan`.

## 3 · High-level breakdown ⏸

**planner** → `docs/HLD.md` (+ DS framing when relevant). Render the data-flow diagram,
send it with a ≤10-line summary; Approve / Request changes / Reject; loop until approved.

## 4 · LLD + conventions + packages ⏸

1. **researcher** (unless skipped by cost mode) → `docs/research.md`.
2. **architect** → `docs/LLD.md`, `docs/CONVENTIONS.md`, and `.devteam/scopes.json`
   if the project's folder layout differs from the defaults in `scopes.json`.
3. Render component/sequence diagrams, the package table and the layer map.
4. **Group the architect's Tier 1 items**: genuine trade-offs (real alternatives) become
   decision cards, max 4 per AskUserQuestion call; forced or obvious choices (dictated by
   the problem, a compatibility constraint, or a prior decision) are shown in the package
   table and approved with the LLD. Then ask: Approve LLD + conventions + packages /
   Request changes / Reject. Log every answer in DECISIONS.md (in the plan worktree).

## 5 · Environment setup (⏸ before installs)

1. **env-setup** phase 1 → install plan (no installs). Show it; Install / Edit / Cancel.
2. Phase 2 → install, `scripts/check.sh` (+ `CHECK_NO_COVERAGE=1` support for the empty
   skeleton), configs, pre-commit, smoke check. Visual: terminal images.

## 6 · Task list, then merge the plan

1. **planner** → `TASKS.md` (milestones; per task ID, owner, deps, status `Backlog`,
   2–5 checkable acceptance criteria).
2. Planning result card (HLD + LLD + env + task count). On approval, **git-pr** runs
   `$TASKGIT approve <repo> plan "chore: plan, design, environment and task list" --keep-shared`.
3. Mirror the current milestone in the task widget (TaskCreate).

## 7 · Build loop

For each milestone, take every `Backlog` task whose dependencies are `Done`. Run
independent tasks in parallel (each has its own worktree; shared files are only edited on main).

Per task `T-xx`:
1. `$TASKGIT start <repo> T-xx`; write `TASK_PROGRESS.md`; mark it `In progress` in the widget.
2. Owner agent (step protocol). `DECISION NEEDED` → record it in TASK_PROGRESS.md,
   checkpoint, ask the owner, resume with the answer.
3. **tester** → `scripts/check.sh` must pass. Then write the diff:
   `$TASKGIT diff <repo> T-xx > <wt>/.results/T-xx/changes.diff` → **reviewer** (reads it).
   Failing checks or Critical/Major findings → **debugger** or the owner agent
   (max rounds per cost mode), then test + review again. Rounds exhausted → decision card.
   ML/DS tasks: also **evaluator** where metrics apply.
4. `$TASKGIT sync <repo> T-xx`: merges current main, re-runs `check.sh`.
   Exit 4 (conflict) or 5 (checks fail) → **debugger** with the output, back to step 3.
5. Classify risk (`approval-modes.md`). Produce the visuals (`visual-capture.md`); screenshots first.
6. Result card (`result-card.md`; changes from `$TASKGIT diffstat`), shown now or queued for a
   batch card per approval mode. Approve / Request changes / Reject:
   - **Approve** → **git-pr** runs `$TASKGIT approve <repo> T-xx "<msg>"` (re-syncs and
     re-checks if main moved; the approval covers the push). Then update `TASKS.md`
     (Done + result + commit), `DECISIONS.md` (Tier 1 answers + agents' Tier 2 lines) and
     `STATE.md` **in the main checkout**, and run `$TASKGIT record <repo> "chore: record T-xx"`.
   - **Request changes** → back to step 2 with the owner's words, same branch.
   - **Reject** → **git-pr** runs `$TASKGIT reject`; set Backlog + reason; `record`.
   - Non-zero exit from approve: 4/5 → debugger then a new card; 7 → report the push
     problem to the owner; never retry blindly.

**Milestone end ⏸**: **docs** updates README/architecture on task `M<n>-docs` (normal task
flow). Then the milestone card; Approve milestone / Request changes.

Project end: **devops** adds CI (deploys only if the owner asks: GCP, Vercel or Render).

## Resume

`/setup-project resume <repo>` or "continue" (details in `checkpointing.md`):
1. Reuse `~/projects/<repo>` or clone it (gh, or add_repo + clone).
2. Read STATE.md / TASKS.md / DECISIONS.md on main; `$TASKGIT list <repo>`.
3. Per open wip branch: `$TASKGIT start` (restores the worktree), read TASK_PROGRESS.md,
   `uv sync` / `npm ci` (already approved), run `check.sh` once if code steps are ✅,
   re-ask any open decision, restart the first step that isn't ✅.
4. Tell the owner in one line where it resumed, then continue.

## Rules

- Tier 1 always goes to the owner; unsure of the tier → Tier 1.
- Every result has a visual; text-only only when nothing can be rendered.
- Never force-push, change repo visibility or commit secrets. Never leave servers running.
- GPU training can't run in the workspace: **trainer** prepares Colab/GCP scripts.
- Mobile-readable messages: tables ≤5 columns, images over long text.
