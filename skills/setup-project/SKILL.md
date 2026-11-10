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
  version: "0.6.0"
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
2. Spawn the agent **fresh** with `description: "<id> · <step>"` (e.g. `T-04 · implement`: the agent
   panel shows it on the agent's status row) and always `subagent_type: "dev-team-setup:<agent>"` (the scope guard
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
   to STATE.md "Context additions". Checkpoint `"<step> done"`. Only then spawn the next agent
   (the one exception: tester and reviewer run together, see `stage-7-build.md` step 3).

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

## Start here

1. **Surface check, before anything else.** This skill needs the Agent tool (to spawn the
   team) and Bash (git, checks, the guard). If either is missing from your tools, e.g. in
   claude.ai chat, reply in one line: "/setup-project needs Claude Code: it spawns a team of
   agents and runs git and tests, which this app can't do." Then stop. Never run the stages
   yourself without the team and the guard.
2. Read the file for the stage you are in, **when it starts**, and only that one: they are not
   needed up front, and every file you read stays in your context for the rest of the session.

| Stage | Read |
|---|---|
| 0 Intake + repo | `references/stage-0-intake.md` |
| 1 Spec · 2 HLD · 3 Team · 4 LLD · 5 Env · 6 Tasks | `references/stage-1-6-planning.md` |
| 7 Build loop, milestone end | `references/stage-7-build.md` |
| 8 Handover | `references/stage-8-handover.md` |
| Change request, pause, abandon | `references/anytime.md` |
| `/setup-project resume <repo>`, or "continue" in a folder with a setup-project STATE.md | `references/resume.md` |

## Rules

- Tier 1 always goes to the owner; unsure of the tier → Tier 1.
- Every result has a visual; text-only only when nothing can be rendered.
- Never force-push, change repo visibility or commit secrets. Never leave servers running.
- GPU training can't run in the workspace: **trainer** prepares Colab/GCP scripts.
- Mobile-readable messages: tables ≤5 columns, images over long text.
