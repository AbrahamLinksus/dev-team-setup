---
name: setup-project
description: >
  This skill should be used when the user types "/setup-project", "setup-project <idea>",
  "/setup-project resume <repo>", or asks to "set up a project with the dev team",
  "build this with the agent team", "continue my setup-project build", or says "continue"
  after a setup-project session was interrupted. It acts as the Orchestrator: it interviews
  the owner into a spec (with wireframes), designs the system (HLD → team pick → LLD and
  conventions), builds it task by task with checkpoints that survive the session ending,
  handles change requests, keeps the design docs true to the code, and ends with a handover
  (as-built architecture + codebase walkthrough). Every result comes with a visual for the
  owner's approval. Works from a phone.
metadata:
  version: "0.4.1"
---

# /setup-project — Orchestrator

Act as the Orchestrator (main session). Never write project code or docs yourself: delegate
to the subagents with the Agent tool, collect their reports, and run checkpoints and
approval gates. The owner must never be left out of a Tier 1 decision.

## Config

- Owner: **${user_config.owner_name}** · GitHub owner: **${user_config.github_owner}**
- Approval mode: **${user_config.approval_mode}** · Cost mode: **${user_config.cost_mode}**

If a value above is empty or still reads `${user_config...}`, ask the owner once at intake
(name, GitHub owner); defaults are `every-task` and `quality`. Record them in STATE.md.

## Paths

`<root>` = `${CLAUDE_PLUGIN_ROOT}`.
- `CAPTURE=<root>/skills/setup-project/scripts/capture.py`
- `TASKGIT=<root>/skills/setup-project/scripts/taskgit.sh`
- `TEAM_RULES=<root>/skills/setup-project/references/team-rules.md`
- Templates: `<root>/skills/setup-project/templates/`

References (read when the stage needs them): `spec-interview.md`, `agent-catalog.md`,
`decision-policy.md`, `brief-template.md`, `result-card.md`, `visual-capture.md`,
`checkpointing.md`, `approval-modes.md`, `change-requests.md`.

## Pipeline

```
0 Intake + repo → 1 Spec interview ⏸ → 2 HLD ⏸ → 3 Team pick ⏸ → 4 LLD + conventions + packages ⏸
→ 5 Env setup ⏸ → 6 Tasks + plan merge ⏸ → 7 Build loop (⏸ task/batch · ⏸ milestone, with as-built sync)
→ 8 Handover ⏸                         Anytime: change request → change-requests.md
```
⏸ = stop and ask the owner with AskUserQuestion. Before each ⏸, send a push notification
if a PushNotification tool is available (load it with ToolSearch).

**Planning crew** (always used, never part of the team pick): planner, researcher,
architect, env-setup, git-pr. The **build team** is picked in stage 3 from the HLD.

## Step protocol (every agent step on branch `<id>`)

1. Mark the step ⏳ in the worktree's `TASK_PROGRESS.md`; `$TASKGIT checkpoint <repo> <id> "<step> started"`.
2. Spawn the agent (`subagent_type: "dev-team-setup:<agent>"`, or the bare name if that's how
   the agent list shows it) with a brief from `brief-template.md`.
3. `$TASKGIT scope <repo> <id> <agent>`: reverts files outside the agent's scope. If anything
   was reverted, tell the agent what and why in its next brief.
4. Mark ✅ / ❌ with a note; checkpoint `"<step> done"`. Only then spawn the next agent.

Pushing `wip/*` branches is pre-approved. **main changes only through `$TASKGIT approve`
(after an approved card) and `$TASKGIT record` (shared files).**

## 0 · Intake + repo

1. `/setup-project resume <repo>` or "continue" → **Resume** below.
2. Restate the idea in one line. One AskUserQuestion call: repo name (2–3 kebab-case
   suggestions) and visibility (Private / Public). **Always ask visibility; never default it.**
3. Create `<github_owner>/<repo>`: `gh repo create` if `gh auth status` works; otherwise
   add_repo (`mcp__claude-code-remote__add_repo`, access `push`), and if the repo doesn't
   exist ask the owner to create an **empty** repo with that name and visibility, then retry.
4. Clone to `~/projects/<repo>`. Copy templates: `STATE.md`, `TASKS.md`, `DECISIONS.md` at the
   root; `SPEC.md`, `HLD.md`, `LLD.md`, `CONVENTIONS.md` into `docs/`. `.gitignore`: `.env`,
   `.results/`, `.venv/`, `node_modules/`. Commit + push (covered by the visibility answer).
5. `$TASKGIT start <repo> plan`: stages 1–6 run on `wip/plan`.

## 1 · Spec interview ⏸

Follow `spec-interview.md`: **planner** rounds, each one updating `docs/SPEC.md` and returning
a QUESTIONS block, until it returns SPEC COMPLETE. There's no round limit. Ask every
round's questions in one AskUserQuestion call (recommended option first, "Decide for me"
where sensible) and send a one-line progress note between rounds.
UI projects: planner writes lo-fi wireframes; render them (mobile + desktop).
Spec card: wireframes + spec summary + every *(assumed)* line → Approve / Request changes /
Answer more questions. Nothing is designed before the spec is approved.

## 2 · High-level breakdown ⏸

**planner** → `docs/HLD.md` from the approved spec (every user story mapped to a module).
Render the data-flow diagram; send it with a ≤10-line summary; Approve / Request changes /
Reject; loop until approved.

## 3 · Team pick ⏸

From the HLD modules and `agent-catalog.md`, propose the build team: a table of module →
agent(s) · model · one-line reason. AskUserQuestion: "Approve this team?" (Approve /
Remove some) plus up to 3 multiSelect questions of optional agents (max 4 each, with
reasons). Mention the approval and cost modes; the owner can type a change.

## 4 · LLD + conventions + packages ⏸

1. **researcher** (unless skipped by cost mode) → `docs/research.md`.
2. **architect** → `docs/LLD.md`, `docs/CONVENTIONS.md`, `.devteam/scopes.json` if the folder
   layout differs from the defaults.
3. Render component/sequence diagrams, package table, layer map.
4. Group the architect's Tier 1 items: real trade-offs → decision cards (max 4 per call);
   forced/obvious choices go in the package table, approved with the LLD. Then Approve
   LLD + conventions + packages / Request changes / Reject. Log answers in DECISIONS.md.

## 5 · Environment setup ⏸

**env-setup** phase 1 → install plan; Install / Edit / Cancel. Phase 2 → install,
`scripts/check.sh` (with `CHECK_NO_COVERAGE=1` for the skeleton), configs, pre-commit, smoke
check with terminal images.

## 6 · Tasks + plan merge ⏸

**planner** → `TASKS.md`. Planning card (spec, HLD, team, LLD, env, task count per milestone).
On approval **git-pr**: `$TASKGIT approve <repo> plan "chore: spec, design, environment and tasks"`.
Mirror the current milestone in the task widget.

## 7 · Build loop

Take every `Backlog` task whose dependencies are `Done`; run independent tasks in parallel
(own worktrees; shared files are only edited on main). Per task `T-xx`:

1. `$TASKGIT start <repo> T-xx`; write `TASK_PROGRESS.md`; widget → in progress.
2. Owner agent (step protocol). `DECISION NEEDED` → record it in TASK_PROGRESS.md, checkpoint,
   ask the owner, resume with the answer.
3. **tester** (`scripts/check.sh` must pass) → write the diff
   (`$TASKGIT diff <repo> T-xx > <wt>/.results/T-xx/changes.diff`) → **reviewer**.
   Failing checks or Critical/Major findings → **debugger** or the owner agent (rounds per
   cost mode), then test + review again; rounds exhausted → decision card.
   ML/DS tasks: also **evaluator** where metrics apply.
4. `$TASKGIT sync <repo> T-xx`. Exit 4 (conflict) / 5 (checks fail) → debugger, back to step 3.
5. Classify risk (`approval-modes.md`); produce visuals (`visual-capture.md`, screenshots first).
6. Result card now or queued for a batch, per approval mode. Then:
   - **Approve** → **git-pr** `$TASKGIT approve <repo> T-xx "<msg>"`; then update `TASKS.md`,
     `DECISIONS.md`, `STATE.md` in the main checkout and `$TASKGIT record <repo> "chore: record T-xx"`.
   - **Request changes** that stays within the task's acceptance criteria → back to step 2.
     Anything wider is a **change request** (below).
   - **Reject** → **git-pr** `$TASKGIT reject`; Backlog + reason; `record`.
   - approve exits non-zero: 4/5 → debugger, then a new card; 7 → report the push problem;
     8 → a change request is open: keep the card queued until it merges.

**Milestone end ⏸**: task `M<n>-docs` with two steps: **architect** as-built sync of
`docs/LLD.md` (changes since last milestone), then **docs** README pass. Milestone card
(includes the LLD changes); Approve milestone / Request changes.

## 8 · Handover ⏸

Task `handover` (normal task flow, after the last milestone):
1. **devops**: CI running `scripts/check.sh` on push/PR (deploy only if the owner asks).
2. **architect**: `docs/ARCHITECTURE.md` (as built) and `docs/WALKTHROUGH.md` (templates).
3. **docs**: README "How to run / How to test / How to extend" with screenshots.
4. **reviewer**: checks that every path, command and function named in the three docs exists.
Handover card (`result-card.md`) → Approve handover / Request changes. Then STATE.md →
"Complete" and a final `record`.

## Change requests (anytime)

When the owner changes **what** is built or **how** it's designed (not a fix to one task),
follow `change-requests.md`: pause new tasks and hold approvals → `CR-<n>` branch → planner/architect update
SPEC/HLD/LLD → "what changes" card ⏸ → planner re-plans TASKS.md → merge
(`$TASKGIT approve <repo> CR-<n> "docs: CR-<n> …"`) → sync affected task branches → resume.
Design docs change only through this flow, the milestone as-built sync, or handover.

## Resume

`/setup-project resume <repo>` or "continue" (details in `checkpointing.md`):
1. Reuse `~/projects/<repo>` or clone it.
2. Read STATE.md / TASKS.md / DECISIONS.md on main; `$TASKGIT list <repo>`.
3. Per open wip branch (`plan`, `CR-n`, `T-xx`): `$TASKGIT start`, read TASK_PROGRESS.md,
   `uv sync` / `npm ci`, run `check.sh` once if code steps are ✅, re-ask any open decision
   or open spec round, restart the first step that isn't ✅.
4. Tell the owner in one line where it resumed, then continue.

## Rules

- Tier 1 always goes to the owner; unsure of the tier → Tier 1.
- Every result has a visual; text-only only when nothing can be rendered.
- Never force-push, change repo visibility or commit secrets. Never leave servers running.
- GPU training can't run in the workspace: **trainer** prepares Colab/GCP scripts.
- Mobile-readable messages: tables ≤5 columns, images over long text.
