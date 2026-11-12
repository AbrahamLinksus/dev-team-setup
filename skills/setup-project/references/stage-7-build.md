# Stage 7 · Build loop

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 7 · Build loop

**Schedule from the graph, never by eye.** `python3 $TASKGRAPH <repo>/TASKS.md --ready` prints the
tasks to start now: dependencies `Done`, no file in their `Files:` shared with a running task, up to
3 running in total, longest remaining chain first. Run it whenever a task finishes, is approved or
waits on a card; tasks run in their own worktrees, and shared files are only edited on main.

**Start the ready tasks together, really at the same time.** Agents run in parallel only when
they're spawned in the **same message**; one Agent call per message runs them one after another.
`$TASKGIT start` each task `--ready` printed, mark each step ⏳ and checkpoint, then send **one message
with one Agent call per task** (each with its own brief, worktree path and port). Handle each
task's REPORT as it comes back and carry on with that task alone; when one finishes or waits on a
card, run `--ready` again and start what it prints the same way. More than 3 at once makes the
checks compete for the machine and the owner's cards pile up.

**Don't let the team idle while a card waits.** Waiting for the owner is most of a build's
wall-clock time, and a question blocks your turn until it's answered. So before you ask a
task's approval question (any approval mode), when another task is independent of it (no
dependency, no shared files in their planned scope):
- If your Agent tool can run an agent in the background (it has a `run_in_background`
  parameter), start that task's first step in the background, then ask. Collect its REPORT
  after the answer.
- Otherwise, first take that task up to its own card, then ask both approval questions in one
  AskUserQuestion call (at most 4 questions): one interruption instead of two.
A rejection costs nothing extra: the other task never depended on it.

**Stall watchdog.** Whenever you mark an agent step started, also start
`$TASKGIT watch <repo> <id> <step>` with the Bash tool in the background (`run_in_background`).
It ends by itself when the step is marked done or failed (exit 0: nothing to do). **Exit 9**
prints a `STALLED:` line: the step has run over 3× its usual time on earlier tasks, or 20 minutes.
Then don't keep waiting: look at the agent's status row (`⚠️ stalled?` after 20 minutes) and
`git -C <wt> log -1`, send a push notification with the STALLED line if the tool exists, and
either start one more watch (the agent is clearly progressing) or stop the agent and spawn the
step fresh (its partial files are on the branch). Without background Bash, skip the watch.

Per task `T-xx`:

1. `$TASKGIT start <repo> T-xx` (a new worktree gets the locked dependencies installed: `uv sync`,
   `npm ci`, …; a warning names the log if that fails, then give it to env-setup before any code step);
   write `TASK_PROGRESS.md`; widget → in progress; set its `Status: In progress` in TASKS.md in the
   main checkout (`--ready` reads it there; the next approve or record commits it).
2. Owner agent (step protocol). A task with two owners (`Owner: backend-coder, frontend-coder`)
   gets one implement step per owner, in the listed order, in the same worktree. `DECISION NEEDED` → record it in TASK_PROGRESS.md, checkpoint,
   ask the owner, resume with the answer.
3. **tester and reviewer in parallel.** Write the owner agent's diff to a file without opening it
   (`$TASKGIT diff <repo> T-xx > <wt>/.results/T-xx/changes.diff`), run
   `$TASKGIT step <repo> T-xx test+review started` (both rows ⏳, `"test+review started"`), then spawn the **tester** (`scripts/check.sh` must pass) and the
   **reviewer** in **one message** (two Agent calls), so they run at the same time. This is the
   one exception to "only then spawn the next agent": the reviewer is read-only and the tester
   only adds tests, so they can't step on each other. When both return: run
   `$TASKGIT step <repo> T-xx test+review done tester "<both one-line results>"`, which runs
   `scope <repo> T-xx tester` **once**. It checks every change since the checkpoint, and
   the reviewer can't have made any (the guard blocks its writes live; its report goes to the
   git-ignored `.results/`). **Never run `scope` as reviewer after this step:** scope checks all
   changes against one role, so it would revert the tester's new tests. The same call marks both
   rows and checkpoints `"test+review done"`; put both REPORTs on the card.
   Coverage below the threshold (everything else green) → back to the **tester** for more tests
   (no new review: tests alone don't change what the reviewer read).
   Other failing checks or Critical/Major findings → **debugger** (`Read:` the failing step's full
   report or `sync-check.txt`, the changed files, the task's LLD sections) or the owner agent
   (rounds per cost mode; later rounds continue the same debugger), then test + review again
   (in parallel, with a fresh `changes.diff`);
   rounds exhausted → decision card.
   ML/DS tasks: also **evaluator** where metrics apply.
   **Small and medium projects (STATE.md "Size"): one agent per low-risk task.** A task that is
   low-risk by its planned scope (none of the high-risk file kinds in `approval-modes.md`) gets
   `$TASKGIT coder-tests <repo> T-xx` right after `start`, `Tests: coder` in TASK_PROGRESS.md and
   `Tests: yours` in the owner agent's brief: the coder writes the tests to the tester's standard
   and runs plain `scripts/check.sh` (coverage included) until it passes. Its REPORT carries the
   check result, so this step is skipped: mark the test and review steps `⏭ coder` and
   `⏭ batched`, and put "Tests by the coder · review batched at milestone end" on its card. Its
   review comes once per milestone (below), one reviewer for all such tasks instead of one each.
   The **tester spawns only on failure**: if the coder's REPORT shows coverage still short, spawn
   the tester for that task (no new review); any other failing check goes to the **debugger** as
   above, which makes the task high-risk.
   The gates (`check.sh`, coverage and lint configs) stay closed to the coder. Large projects,
   and every task whose scope is high-risk, keep the separate tester and per-task reviewer; a
   debugger round or a Major finding turns the task high-risk, and its next round has both.
4. `$TASKGIT sync <repo> T-xx`. Exit 4 (conflict) / 5 (checks fail; output path in the error)
   → debugger, back to step 3.
5. **Plan vs actual:** `$TASKGIT changed <repo> T-xx | python3 $TASKGRAPH <repo>/TASKS.md --undeclared T-xx`
   lists the files the task changed outside its `Files:`. Any → add them to its `Files:` in TASKS.md
   in the main checkout straight away (so `--ready` keeps tasks that touch them waiting), put a
   `Plan vs actual:` line on the card, and run `--ready` again: the schedule for the remaining
   tasks now reflects them.
   Classify risk (`approval-modes.md`); produce visuals (`visual-capture.md`, screenshots first).
   Run `python3 $COST …` for the card's Cost line. **Exit 3 (over budget)** → before the card, a
   decision card ⏸: "Spent $X of your $B budget" → **Raise the budget to …** (suggest 1.5×; record it
   in STATE.md and use it from now on) / **Pause** (`anytime.md`). Never continue over budget unasked.
6. Result card now, queued for a batch, or (autopilot, low-risk with every goal ✅) approved first
   and sent afterwards with Undo, per approval mode (`approval-modes.md`). Then:
   - **Approve** → first update `TASKS.md` (status `Done`, Result line), `DECISIONS.md` and
     `STATE.md` in the main checkout, then run `$TASKGIT approve <repo> T-xx "<msg>"` yourself, with
     a conventional-commit message built from the card (`feat(auth): add login endpoint [T-07]`).
     approve commits those updates in the task's own commit: one commit per task, no `record`.
     If approve fails, the updates stay in the main checkout; fix the cause and approve again.
   - **Request changes** that stays within the task's acceptance criteria → back to step 2,
     continuing the owner agent (see **Rework continuation** in SKILL.md). Anything wider is a
     **change request** (`references/anytime.md`).
   - **Reject** → run `$TASKGIT reject <repo> T-xx` yourself; Backlog + reason; `record`.
   - approve exits non-zero: 4/5 → debugger, then a new card; 7 → report the push problem;
     8 → a change request is open: keep the card queued until it merges.

**Batched review** (first, whenever any task in the milestone had its review batched): in the
milestone's last worktree (`M<n>-docs`, or `handover` for the last milestone), write those tasks'
approved diffs to one file without opening it:
`for id in T-03 T-05; do git -C <repo> show "$(git -C <repo> log -n 1 --format=%H --grep="^Task: $id\$" main)"; done > <wt>/.results/<task>/changes.diff`
and spawn one **reviewer** on it (brief: the task IDs and their acceptance criteria; for tasks
with `Tests: coder`, also check that the tests really exercise each criterion). Critical or
Major findings → a fix task per affected task (`T-03r`, its owner agent, high-risk, normal flow)
before the milestone card; Minor findings go on the milestone card.

**Milestone end ⏸** (every milestone but the last): task `M<n>-docs` with two steps: **architect** as-built sync of
`docs/LLD.md` (changes since last milestone, section numbers kept stable), then **docs**
README pass. Write the milestone's changed files to `<wt>/.results/M<n>-docs/changed-files.txt`
(`git -C <repo> diff --name-only <last milestone's commit> main`, without opening it) and put it in
the architect's `Read:`: the sync edits only the LLD sections for those paths. **Skip the sync**
(mark it `⏭ no design changes`) when no changed path outside `docs/`, tests and the shared files
appears in `docs/LLD.md` (`grep -c -F -f` on the list's top folders finds nothing). Milestone card (includes the LLD changes): **Approve + continue in a fresh
session (Recommended)** / Approve and continue here / Request changes.
Fresh session → update STATE.md "Next step", `$TASKGIT record <repo> "chore: milestone M<n>"`,
then tell the owner: "Start a new chat and run `/setup-project resume <repo>`", and stop.
**The last milestone** has no docs task and no milestone card: its last approved task leads
straight into the handover (stage 8), whose architect and docs steps cover the same ground.
Each milestone costs a docs task and a session restart, so the planner places them only at risk
checkpoints (first end-to-end flow, data model locked, first integration, before deploy).

**Long session check (between tasks).** Your own context grows with every task, and every call
re-reads all of it, so a long session costs more per task the longer it runs. After you
approve a task, if **6 or more tasks** have been approved in this session, no task
is mid-step (every open `TASK_PROGRESS.md` has no ⏳) and the milestone isn't about to end
(its last task isn't next), ask once: **Continue in a fresh session (Recommended)** / Continue
here. Fresh session: the same steps as at milestone end (STATE.md "Next step", `record`, tell
the owner to resume, stop). Continue here: don't ask again until another 6 tasks are approved.
In unattended mode this counts like a milestone: answer Recommended and log `SESSION DONE`.
