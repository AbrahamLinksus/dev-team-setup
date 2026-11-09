# Checkpointing and resume

## Where work lives

| Thing | Location | Survives the session ending? |
|---|---|---|
| Approved work | `main` (pushed) | ✅ |
| Planning in progress (HLD/LLD/env) | branch `wip/plan`, worktree `<repo>-wt/plan` | ✅ (pushed at every checkpoint) |
| Task in progress | branch `wip/<task-id>`, worktree `<repo>-wt/<task-id>` | ✅ (pushed at every checkpoint) |
| Step states, debugger round, open decision | `TASK_PROGRESS.md` on the wip branch | ✅ |
| Images in `.results/` | worktree only (git-ignored) | ❌ (re-capture on resume if needed) |

## TASK_PROGRESS.md format

```
# T-07 · Login API
Owner: backend-coder · Started: 2026-11-09 14:20 IST

| Step | Agent | Status | Note |
|---|---|---|---|
| 1 Implement | backend-coder | ✅ | auth.py, routes.py |
| 2 Tests + checks | tester | ✅ | 14/14, coverage 86% |
| 3 Review | reviewer | ⏳ | |
| 4 Visual | orchestrator | ⬜ | |
| 5 Result card | orchestrator | ⬜ | |

Debugger rounds: 0/3
Open decision: none
<!-- or: Open decision: D-12 token expiry — options A) 15 min B) 1 h — asked 14:32 -->
Jake's change requests: none
```

Status: ⬜ pending · ⏳ in progress · ✅ done · ❌ failed.

## Protocol for each step

1. Set the step to ⏳ and checkpoint: `$TASKGIT checkpoint <repo> <id> "<step> started"`.
2. Spawn the agent.
3. When it returns: set ✅ (or ❌ with the reason), add the note, checkpoint
   `"<step> done"`.
4. Only then spawn the next agent.

A step marked ⏳ on resume was interrupted: restart it from the beginning (its partial
files are on the branch; the agent reads them and continues).

## Resume algorithm

```
repo present locally?         → reuse; else clone (gh) or add_repo + clone
$TASKGIT list <repo>          → open wip branches (plan, T-xx…)
for each branch:
    wt = $TASKGIT start <repo> <id>          # restores worktree from origin
    read wt/TASK_PROGRESS.md
    uv sync / npm ci in wt                   # deps are already approved
    if any step ✅ involved code: run scripts/check.sh once
        fails → mark the failing step ⏳ again and restart from it
    open decision? → ask Jake again (AskUserQuestion)
    else → restart the first step that isn't ✅
no wip branches               → read STATE.md "Next step" and continue from TASKS.md
```

Tell Jake in one line where it resumed, e.g. "Resumed todo-app at T-07 · review step
(coder ✅, tester ✅)".
