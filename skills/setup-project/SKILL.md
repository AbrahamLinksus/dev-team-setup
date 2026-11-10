---
name: setup-project
description: >
  This skill should be used when the user types "/setup-project" followed by an idea,
  "/setup-project resume" followed by a repo name, or asks to "set up a project with the dev team",
  "build this with the agent team" or "continue my setup-project build". A bare "continue"
  counts only when the current folder holds a setup-project repo (a STATE.md written by this
  skill) or the message names the repo; otherwise it belongs to whatever else the user was
  doing. It acts as the Orchestrator: it interviews
  the owner into a spec (with wireframes), designs the system (HLD → team pick → LLD and
  conventions), builds it task by task with checkpoints that survive the session ending,
  handles change requests, keeps the design docs true to the code, and ends with a handover
  (as-built architecture + codebase walkthrough). Every result comes with a visual for the
  owner's approval. Works from a phone.
metadata:
  version: "0.5.1"
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
Timestamps you write (STATE.md, TASK_PROGRESS.md) use the owner's local time with its UTC offset
(`date +'%Y-%m-%d %H:%M %:z'`), never a fixed zone.
If the prompt contains `Answers file: <path>`, read `references/unattended.md` first and follow
it for the whole run: every owner question is answered from that file, never AskUserQuestion.

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
Cards and images go out with SendUserFile / SendUserMessage where they exist; in the terminal
CLI they don't, so follow the fallback in `result-card.md` (card file + printed image paths).

**Planning crew** (always used, never part of the team pick): planner, researcher,
architect, env-setup. The **build team** is picked in stage 3 from the HLD. Approve, reject and
record are one script call each, so you run `$TASKGIT` yourself rather than spawning an agent
for them (git-pr stays available for a task whose commit message needs real summarising).

## Step protocol (every agent step on branch `<id>`)

1. Mark the step ⏳ in the worktree's `TASK_PROGRESS.md`; `$TASKGIT checkpoint <repo> <id> "<step> started"`.
2. Spawn the agent **fresh** (always `subagent_type: "dev-team-setup:<agent>"`: the scope guard
   only recognises the prefixed name, so a bare name would run unguarded) with a brief from `brief-template.md`: `Read:` built from
   the role default + the task's `Context:` + STATE.md "Context additions", and
   `Write full report to: <wt>/.results/<id>/<step>-<agent>.md`. Every path in a brief is
   absolute (`<wt>` = the worktree path `start` printed): subagents don't start in the worktree. Rework is the only exception
   (see **Rework continuation**). Record the returned agent ID in TASK_PROGRESS.md
   (`Agents: backend-coder=<id>, debugger=<id>`).
3. `$TASKGIT scope <repo> <id> <agent>`: reverts files outside the agent's scope. If anything
   was reverted, tell the agent what and why in its next brief.
4. Mark ✅ / ❌ and copy the one-line result of the short REPORT into the step's note
   (e.g. `5/5 goals ✅ · checks pass · 2 decisions`). A `Context gap:` in the REPORT → add a row
   to STATE.md "Context additions". Checkpoint `"<step> done"`. Only then spawn the next agent.

## Context budget (Orchestrator)

- Never read diffs, logs, test output, check output or full reports into your own context.
  Write them to files (`$TASKGIT diff … > file`, captures, full reports) and pass the
  **paths** to the next agent's `Read:` field. `$TASKGIT diffstat` (a summary) is fine.
- Work from the short REPORTs. Open a full report only when a card needs a specific detail
  the REPORT doesn't have (e.g. the architect's `## Needs the owner's approval` list for
  decision cards, the planner's `## Task impact` for a CR card), and read just that section.
- Briefs list exactly what to read; don't paste documents into briefs.

## Rework continuation

- Default: a fresh spawn for every step.
- Continue an agent (SendMessage to its ID from TASK_PROGRESS.md `Agents:`) only for rework on
  the **same task**: "Request changes" within the task's acceptance criteria → continue the
  owner agent with the owner's words; further debugger rounds on one task → continue the same
  debugger with the new failure-output path.
- Spawn fresh instead when: the task is different, the session was resumed, the ID is unknown,
  SendMessage isn't available, or that agent has already been continued twice. A fresh rework
  brief carries the previous short REPORT and the owner's change request (`Rework:` field).
- Never continue an agent across tasks or worktrees.

Pushing `wip/*` branches is pre-approved. **main changes only through `$TASKGIT approve`
(after an approved card) and `$TASKGIT record` (shared files).**

## 0 · Intake + repo

0. **Surface check, before anything else.** This skill needs the Agent tool (to spawn the
   team) and Bash (git, checks, the guard). If either is missing from your tools, e.g. in
   claude.ai chat, reply in one line: "/setup-project needs Claude Code: it spawns a team of
   agents and runs git and tests, which this app can't do." Then stop. Never run the stages
   yourself without the team and the guard.
1. `/setup-project resume <repo>`, or "continue" when this folder has a setup-project STATE.md
   (or the message names the repo) → **Resume** below.
2. Check `python3 --version` (3.9 or newer). The scope guard that keeps every agent in its lane
   runs on it; without it, the guard blocks every agent call. Missing → tell the owner what to
   install and stop: never build without the guard.
   Then run `python3 $CAPTURE doctor` (the plugin's own tooling for visuals: Playwright + Chromium,
   Pillow, markdown, npm for Mermaid). If it reports anything missing, ask once (AskUserQuestion:
   **Install the visual tools** into the plugin's private venv / **Skip visuals** = text cards),
   then run `python3 $CAPTURE doctor --install`. It never touches the project's environment.
   Record the answer in STATE.md.
3. Restate the idea in one line. One AskUserQuestion call: repo name (2–3 kebab-case
   suggestions) and visibility (Private / Public). **Always ask visibility; never default it.**
4. Create `<github_owner>/<repo>`: `gh repo create` if `gh auth status` works; otherwise
   add_repo (`mcp__claude-code-remote__add_repo`, access `push`), and if the repo doesn't
   exist ask the owner to create an **empty** repo with that name and visibility, then retry.
5. Clone into the session's working folder: `<base>/<repo>`, where `<base>` is the folder this
   session runs in (`pwd`). Task worktrees then live next to it in `<base>/<repo>-wt/`, so every
   file the team writes is inside a folder Claude Code already trusts. Anywhere else (e.g.
   `~/projects`) each edit asks for permission, and remote or phone sessions refuse outright.
   If `<base>` is itself a git checkout (the session was started inside another project), ask
   the owner for a folder, then add it with `/add-dir <folder>` before cloning there.
   Record `<base>` in STATE.md. Copy templates: `STATE.md`, `TASKS.md`, `DECISIONS.md` at the
   root; `SPEC.md`, `HLD.md`, `LLD.md`, `CONVENTIONS.md` into `docs/`. `.gitignore`: `.env`,
   `.results/`, `.venv/`, `node_modules/` (env-setup adds the data and model ignores for data/ML work). Commit + push (covered by the visibility answer).
6. `$TASKGIT start <repo> plan`: stages 1–6 run on `wip/plan`.

## 1 · Spec interview ⏸

Follow `spec-interview.md`: **planner** rounds, each one updating `docs/SPEC.md` and returning
a QUESTIONS block, until it returns SPEC COMPLETE (at most 6 rounds; then open items become
assumptions listed on the spec card). Ask every
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

**env-setup** phase 1 → install plan; **Install** / **Edit** (the owner says what to change →
env-setup redoes phase 1) / **Cancel** (nothing is installed: back to the LLD's package table at
stage 4 to pick different packages, or **Pause** the project, see below). Phase 2 → install,
`scripts/check.sh` (with `CHECK_NO_COVERAGE=1` for the skeleton), configs, pre-commit, smoke
check with terminal images.

## 6 · Tasks + plan merge ⏸

**planner** → `TASKS.md`. Planning card (spec, HLD, team, LLD, env, task count per milestone).
On approval run `$TASKGIT approve <repo> plan "chore: spec, design, environment and tasks"` yourself.
Mirror the current milestone in the task widget.

## 7 · Build loop

Take every `Backlog` task whose dependencies are `Done`; run independent tasks in parallel
(own worktrees; shared files are only edited on main). Per task `T-xx`:

1. `$TASKGIT start <repo> T-xx` (a new worktree gets the locked dependencies installed: `uv sync`,
   `npm ci`, …; a warning names the log if that fails, then give it to env-setup before any code step);
   write `TASK_PROGRESS.md`; widget → in progress.
2. Owner agent (step protocol). `DECISION NEEDED` → record it in TASK_PROGRESS.md, checkpoint,
   ask the owner, resume with the answer.
3. **tester** (`scripts/check.sh` must pass) → write the diff to a file without opening it
   (`$TASKGIT diff <repo> T-xx > <wt>/.results/T-xx/changes.diff`) → **reviewer**.
   Coverage below the threshold (everything else green) → back to the **tester** for more tests.
   Other failing checks or Critical/Major findings → **debugger** (`Read:` the failing step's full
   report or `sync-check.txt`, the changed files, the task's LLD sections) or the owner agent
   (rounds per cost mode; later rounds continue the same debugger), then test + review again;
   rounds exhausted → decision card.
   ML/DS tasks: also **evaluator** where metrics apply.
4. `$TASKGIT sync <repo> T-xx`. Exit 4 (conflict) / 5 (checks fail; output path in the error)
   → debugger, back to step 3.
5. Classify risk (`approval-modes.md`); produce visuals (`visual-capture.md`, screenshots first).
6. Result card now or queued for a batch, per approval mode. Then:
   - **Approve** → run `$TASKGIT approve <repo> T-xx "<msg>"` yourself, with a conventional-commit
     message built from the card (`feat(auth): add login endpoint [T-07]`); then update `TASKS.md`,
     `DECISIONS.md`, `STATE.md` in the main checkout and `$TASKGIT record <repo> "chore: record T-xx"`.
   - **Request changes** that stays within the task's acceptance criteria → back to step 2,
     continuing the owner agent (see **Rework continuation**). Anything wider is a
     **change request** (below).
   - **Reject** → run `$TASKGIT reject <repo> T-xx` yourself; Backlog + reason; `record`.
   - approve exits non-zero: 4/5 → debugger, then a new card; 7 → report the push problem;
     8 → a change request is open: keep the card queued until it merges.

**Milestone end ⏸**: task `M<n>-docs` with two steps: **architect** as-built sync of
`docs/LLD.md` (changes since last milestone, section numbers kept stable), then **docs**
README pass. Milestone card (includes the LLD changes): **Approve + continue in a fresh
session (Recommended)** / Approve and continue here / Request changes.
Fresh session → update STATE.md "Next step", `$TASKGIT record <repo> "chore: milestone M<n>"`,
then tell the owner: "Start a new chat and run `/setup-project resume <repo>`", and stop.

## 8 · Handover ⏸

Task `handover` (normal task flow, after the last milestone):
0. **Screenshots for the docs.** `.results/` is git-ignored and each task's copy is deleted when it
   is approved, so a README can never link into it. The **tester** starts the app in the handover
   worktree and captures it fresh (`$CAPTURE web <url> <wt>/.results/handover/app --mobile`, plus
   a `$CAPTURE term` of the test run), then stops it. You copy the 2–4 best PNGs to
   `<wt>/docs/images/` (tracked) and list those paths in the docs agent's `Read:`.
1. **devops**: CI running `scripts/check.sh` on push/PR (deploy only if the owner asks).
2. **architect**: `docs/ARCHITECTURE.md` (as built) and `docs/WALKTHROUGH.md` (templates).
3. **docs**: README "How to run / How to test / How to extend" with the screenshots in `docs/images/`.
4. **reviewer** (read-only): checks that every path and function named in the three docs exists.
   **tester** (it has Bash): runs every command in the README's "How to run" and "How to test"
   in a fresh clone of the handover branch, each under `timeout`, captures the run with
   `$CAPTURE term`, and reports any command that fails or doesn't exist.
Handover card (`result-card.md`) → Approve handover / Request changes. Then STATE.md →
"Complete" and a final `record`.

## Change requests (anytime)

When the owner changes **what** is built or **how** it's designed (not a fix to one task),
follow `change-requests.md`: pause new tasks and hold approvals → `CR-<n>` branch → planner/architect update
SPEC/HLD/LLD → "what changes" card ⏸ → planner re-plans TASKS.md → merge
(`$TASKGIT approve <repo> CR-<n> "docs: CR-<n> …"`) → sync affected task branches → offer
**Continue in a fresh session (Recommended)** / Continue here (fresh session: same steps as at
milestone end) → resume.
Design docs change only through this flow, the milestone as-built sync, or handover.

## Pause or abandon (anytime)

The owner can say "pause" or "stop" at any card, or pick it from an AskUserQuestion.
- **Pause**: finish nothing new; checkpoint every open `wip/*` branch (they're already pushed),
  set STATE.md `Status: Paused` with the reason and the next step, `$TASKGIT record`, stop any
  server you started. `/setup-project resume <repo>` later continues from STATE.md as usual.
- **Abandon**: ask once to confirm (it can't be resumed). Then `$TASKGIT reject` every open task
  branch, set STATE.md `Status: Abandoned` with the reason, `$TASKGIT record`. The repo and
  everything already on main stay; nothing is deleted on GitHub.

## Resume

`/setup-project resume <repo>`, or "continue" in a folder with a setup-project STATE.md (details in
`checkpointing.md`). Rebuild everything
from STATE.md, TASKS.md, DECISIONS.md and TASK_PROGRESS.md; take nothing from a previous chat.
Agent IDs from earlier sessions are not continued; every step after a resume spawns fresh.
1. Reuse `<base>/<repo>` (the folder recorded in STATE.md, or `./<repo>` in this session's
   folder) or clone it there. Resume from the folder that *holds* the repo, not from inside it:
   the worktrees `<repo>-wt/` sit next to the repo. A repo outside this session's folders (e.g.
   `~/projects/<repo>` from an older run) → `/add-dir` its parent first.
2. Read STATE.md / TASKS.md / DECISIONS.md on main; `$TASKGIT list <repo>`.
   `Status: Paused` → set it back to Active and continue. `Status: Abandoned` or `Complete` → say so
   and ask whether to reopen it before doing anything.
3. Per open wip branch (`plan`, `CR-n`, `T-xx`): `$TASKGIT start` (installs dependencies into a
   restored worktree), read TASK_PROGRESS.md, run `check.sh` once if code steps are ✅, re-ask any open decision
   or open spec round, restart the first step that isn't ✅.
4. Tell the owner in one line where it resumed, then continue.

## Rules

- Tier 1 always goes to the owner; unsure of the tier → Tier 1.
- Every result has a visual; text-only only when nothing can be rendered.
- Never force-push, change repo visibility or commit secrets. Never leave servers running.
- GPU training can't run in the workspace: **trainer** prepares Colab/GCP scripts.
- Mobile-readable messages: tables ≤5 columns, images over long text.
