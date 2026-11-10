# Resume

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

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
4. Send a one-screen **Where we are** (the owner may be back after days, on a phone), then
   continue without waiting unless a decision is open:

   ```
   Where we are · <project> · <Status>
   Stage 7 Build · Milestone 2/3 (Auth + core API) · 7/12 tasks done
   Last done:  T-06 Login page (approved <date>)
   In flight:  T-07 Password reset: review step (resuming now)
   Waiting on you: <open decisions or queued cards, one line each | nothing>
   Recent decisions: D-11 Postgres · D-12 bcrypt · D-13 15-min tokens
   Spent: $3.10 so far · budget $25        (python3 $COST …, leave out if unreadable)
   Next: <STATE.md "Next step">
   ```
   Everything comes from STATE.md, TASKS.md, DECISIONS.md (last three rows) and the open
   TASK_PROGRESS.md files. At most 9 lines; details only if the owner asks.
