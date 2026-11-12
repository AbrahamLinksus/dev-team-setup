# Checkpointing and resume

## Where work lives

| Thing | Location | Survives the session ending? |
|---|---|---|
| Approved work | `main` (pushed) | ✅ |
| Planning in progress (spec/HLD/LLD/env/tasks) | branch `wip/plan`, worktree `<repo>-wt/plan` | ✅ (pushed at every checkpoint) |
| Change request in progress | branch `wip/CR-<n>`, worktree `<repo>-wt/CR-<n>` | ✅ |
| Task in progress | branch `wip/<task-id>`, worktree `<repo>-wt/<task-id>` | ✅ (pushed at every checkpoint) |
| Step states, debugger round, open decision | `TASK_PROGRESS.md` on the wip branch | ✅ |
| Images in `.results/` | worktree only (git-ignored) | ❌ (re-capture on resume if needed) |

## TASK_PROGRESS.md format

```
# T-07 · Login API
Owner: backend-coder · Started: 2026-11-09 14:20 +05:30

| Step | Agent | Status | Note |
|---|---|---|---|
| 1 Implement | backend-coder | ✅ | 3/3 goals ✅ · 4 files · checks pass · 1 decision |
| 2 Tests + checks | tester | ✅ | checks pass · coverage 86% · 14 tests |
| 3 Review | reviewer | ⏳ | |
| 4 Visual | orchestrator | ⬜ | |
| 5 Result card | orchestrator | ⬜ | |

Agents: backend-coder=a1b2c3 (continued 0×), tester=d4e5f6
Debugger rounds: 0/3
Open decision: none
<!-- or: Open decision: D-12 token expiry — options A) 15 min B) 1 h — asked 14:32 -->
the owner's change requests: none
```

Status: ⬜ pending · ⏳ in progress · ✅ done · ❌ failed. The note is the one-line result
from the agent's short REPORT; the full report's path is `.results/<id>/<step>-<agent>.md`.
`Agents:` records each agent's ID and how often it was continued (max 2), for rework only.

On `wip/plan`, TASK_PROGRESS.md also records the spec round (`Spec round: 3 · 9/12 complete`)
and the last QUESTIONS block that hasn't been answered yet, so a resumed session re-asks
exactly those questions. On `wip/CR-<n>` it records the CR text verbatim and the CR step (1–8).

## Protocol for each step

1. `$TASKGIT step <repo> <id> <step> started` (step in lower case: `implement`, `test`, `review`,
   `debug`; `test+review` marks both rows): sets the row ⏳ and checkpoints `<step> started`.
   taskgit logs each checkpoint with a timestamp in `<repo>/.git/devteam-timing.log`, so time per
   step can be measured.
2. Spawn the agent.
3. When it returns, one call: `$TASKGIT step <repo> <id> <step> done <agent> "<note>"` (or
   `failed`, with the reason as the note). It runs `scope` as `<agent>` (reverts out-of-scope
   files), sets ✅/❌ with the note (a step with no row gets one), and checkpoints `<step> done`.
   It never touches other worktrees, so several tasks can be in flight at once.
4. Only then spawn the next agent.

Shared files (`TASKS.md`, `STATE.md`, `DECISIONS.md`) are never changed on task branches
(`checkpoint` reverts them). They're updated in the main checkout just before `approve`, which
commits them in the task's own squash commit (`$TASKGIT record` commits updates that have no task
to approve: rejects, pauses, milestone notes). That's what keeps parallel tasks from conflicting.

A step marked ⏳ on resume was interrupted: restart it from the beginning (its partial
files are on the branch; the agent reads them and continues).

## Resume algorithm

Resume rebuilds everything from files: STATE.md, TASKS.md, DECISIONS.md and each branch's
TASK_PROGRESS.md. Nothing is taken from the previous chat: no remembered reports, no agent
IDs (every step after a resume spawns fresh), no assumptions about what was said. This is
what makes "Approve + continue in a fresh session" safe at milestone ends and after change
requests. Full reports in `.results/` are git-ignored, so after a resume on another
machine only the TASK_PROGRESS.md notes remain; re-run a step if its details are needed.

```
repo present locally?         → reuse (<base>/<repo>, base from STATE.md); else clone into this
                                session's folder (gh, or add_repo + clone)
$TASKGIT list <repo>          → open wip branches (plan, T-xx…)
for each branch:
    wt = $TASKGIT start <repo> <id>          # restores worktree from origin + installs locked deps
    read wt/TASK_PROGRESS.md
    if any step ✅ involved code: run scripts/check.sh once
        fails → mark the failing step ⏳ again and restart from it
    open decision? → ask the owner again (AskUserQuestion)
    else → restart the first step that isn't ✅
no wip branches               → read STATE.md "Next step" and continue from TASKS.md
```

Tell the owner in one line where it resumed, e.g. "Resumed todo-app at T-07 · review step
(coder ✅, tester ✅)".
