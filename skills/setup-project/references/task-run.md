# Task run (the task-runner's procedure)

Read by the **task-runner** agent, which the Orchestrator starts in the background, one per ready
task. It does the task's agent steps itself (nested agents), so the Orchestrator's own context
grows by one short result per task instead of a dozen calls: the whole project fits in one
session, and up to three tasks run at once while the owner answers cards.

## Your brief

```
RUN · <task id> · task-runner
TASKGIT, TEAM_RULES, CAPTURE, TASKGRAPH: <absolute paths>
Repo: <main checkout> · Worktree: <wt> · Port: <n>
Task: TASKS.md entry (title, Owner, Files, Context, acceptance criteria)
Size: <small|medium|large> · Cost mode: <m> · Risk by scope: <low|high> · Tests: <coder|tester>
Resume at: implement | test+review | sync     (a fresh runner after a decision, a file or a rework)
Decision / Needs file granted / Rework: <the owner's answer or change request, verbatim>   (optional)
```

The worktree exists (`$TASKGIT start` ran) and TASK_PROGRESS.md is written. Read, from
`<plugin>/skills/setup-project/`: `SKILL.md` sections **Step protocol**, **Modes** and **Rework
continuation**; `references/stage-7-build.md` steps **2, 3 and 4** of "Per task" (and the
**Needs file** paragraph); `references/brief-template.md`; `references/result-card.md` section
**Per-task card**. Nothing else up front.

## What you do

**Wait for every agent you start.** Every Agent call sets `run_in_background: false`: agents
started by an agent run in the background by default, and a runner that answers while its coder is
still working loses the task (the first test run switched runners off because of exactly this).
Tester and reviewer go in one message, both in the foreground; you continue when both have reported.

1. From `Resume at`: **implement** (step 2; two owners → one step each, in order), **test + review**
   (step 3, tester and reviewer in one message, or `Tests: coder` as step 3 describes; debugger
   rounds per cost mode, continuing the same debugger by its ID), then **sync** (step 4: exit 4 or
   5 → debugger, back to test + review). Every agent step is `$TASKGIT step … started`, the agent,
   `$TASKGIT step … done|failed <agent> "<note>"`. Write diffs with
   `$TASKGIT diff <repo> <id> <wt>/.results/<id>/changes.diff`.
2. **Plan vs actual:** `$TASKGIT changed <repo> <id> | python3 $TASKGRAPH <repo>/TASKS.md --undeclared <id>`.
3. **Risk** (`approval-modes.md` classification) and **visuals** (`visual-capture.md`, through the
   owner agent or tester, never yourself), then write the card to `<wt>/.results/<id>/card.md` in
   the per-task card format, without the Cost line (the Orchestrator adds it).

Stop and return at once when an agent returns `DECISION NEEDED` or `Needs file:`, or when the
debugger rounds run out. Never run approve, reject, record, undo, catchup or lint (the guard
blocks them), never edit TASKS.md, STATE.md or DECISIONS.md, and never ask the owner anything.

## Your answer (exactly one)

```
TASK READY <id>
Goals: <x>/<y> ✅ · <one line per ⚠️ or ❌ goal>
Checks: <the tester's or coder's Checks line>
Review: <the reviewer's SOLID line | batched at milestone end>
Risk: <low|high> · <reason>
Card: <wt>/.results/<id>/card.md · Try this: <path> · Visuals: <paths>
Plan vs actual: none | <paths outside Files>
Agents: <role>=<agent id> …   (for rework)
```
or `DECISION NEEDED` (the agent's block, verbatim) followed by `Resume at: <step>`;
or `NEEDS FILE <id> · <path> · <why> · Resume at: <step>`;
or `BLOCKED <id> · <what failed, after how many debugger rounds> · Report: <full report path>`;
or `NO NESTING` (you have no Agent tool).
