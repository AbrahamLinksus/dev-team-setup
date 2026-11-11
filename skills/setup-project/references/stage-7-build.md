# Stage 7 · Build loop

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 7 · Build loop

Take every `Backlog` task whose dependencies are `Done`; run independent tasks in parallel
(own worktrees; shared files are only edited on main).

**Start independent tasks together, really at the same time.** Agents run in parallel only when
they're spawned in the **same message**; one Agent call per message runs them one after another.
So pick up to **3** ready tasks that don't depend on each other and don't plan to touch the same
files (check their `Context:` and the LLD modules in TASKS.md; when unsure, they're not
independent). `$TASKGIT start` each one, mark each step ⏳ and checkpoint, then send **one message
with one Agent call per task** (each with its own brief, worktree path and port). Handle each
task's REPORT as it comes back and carry on with that task alone; when one finishes or waits on a
card, start the next ready task the same way. More than 3 at once makes the checks compete for the
machine and the owner's cards pile up.

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

Per task `T-xx`:

1. `$TASKGIT start <repo> T-xx` (a new worktree gets the locked dependencies installed: `uv sync`,
   `npm ci`, …; a warning names the log if that fails, then give it to env-setup before any code step);
   write `TASK_PROGRESS.md`; widget → in progress.
2. Owner agent (step protocol). `DECISION NEEDED` → record it in TASK_PROGRESS.md, checkpoint,
   ask the owner, resume with the answer.
3. **tester and reviewer in parallel.** Write the owner agent's diff to a file without opening it
   (`$TASKGIT diff <repo> T-xx > <wt>/.results/T-xx/changes.diff`), mark both steps ⏳, checkpoint
   `"test+review started"`, then spawn the **tester** (`scripts/check.sh` must pass) and the
   **reviewer** in **one message** (two Agent calls), so they run at the same time. This is the
   one exception to "only then spawn the next agent": the reviewer is read-only and the tester
   only adds tests, so they can't step on each other. When both return: run
   `$TASKGIT scope <repo> T-xx tester` **once**. It checks every change since the checkpoint, and
   the reviewer can't have made any (the guard blocks its writes live; its report goes to the
   git-ignored `.results/`). **Never run `scope` as reviewer after this step:** scope checks all
   changes against one role, so it would revert the tester's new tests. Then mark both, checkpoint
   `"test+review done"`, and put both REPORTs on the card.
   Coverage below the threshold (everything else green) → back to the **tester** for more tests
   (no new review: tests alone don't change what the reviewer read).
   Other failing checks or Critical/Major findings → **debugger** (`Read:` the failing step's full
   report or `sync-check.txt`, the changed files, the task's LLD sections) or the owner agent
   (rounds per cost mode; later rounds continue the same debugger), then test + review again
   (in parallel, with a fresh `changes.diff`);
   rounds exhausted → decision card.
   ML/DS tasks: also **evaluator** where metrics apply.
   **Batched review (small and medium projects, STATE.md "Size").** A task that is low-risk by its
   planned scope (none of the high-risk file kinds in `approval-modes.md`) runs the **tester
   alone** in this step: mark its review step `⏭ batched` in TASK_PROGRESS.md and TASKS.md, and put
   "Review: batched at milestone end" on its card. Its review comes once per milestone (below), one
   reviewer for all such tasks instead of one each. Large projects, and every task whose scope is
   high-risk, keep the per-task reviewer.
4. `$TASKGIT sync <repo> T-xx`. Exit 4 (conflict) / 5 (checks fail; output path in the error)
   → debugger, back to step 3.
5. Classify risk (`approval-modes.md`); produce visuals (`visual-capture.md`, screenshots first).
   Run `python3 $COST …` for the card's Cost line. **Exit 3 (over budget)** → before the card, a
   decision card ⏸: "Spent $X of your $B budget" → **Raise the budget to …** (suggest 1.5×; record it
   in STATE.md and use it from now on) / **Pause** (`anytime.md`). Never continue over budget unasked.
6. Result card now, queued for a batch, or (autopilot, low-risk with every goal ✅) approved first
   and sent afterwards with Undo, per approval mode (`approval-modes.md`). Then:
   - **Approve** → run `$TASKGIT approve <repo> T-xx "<msg>"` yourself, with a conventional-commit
     message built from the card (`feat(auth): add login endpoint [T-07]`); then update `TASKS.md`,
     `DECISIONS.md`, `STATE.md` in the main checkout and `$TASKGIT record <repo> "chore: record T-xx"`.
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
and spawn one **reviewer** on it (brief: the task IDs and their acceptance criteria). Critical or
Major findings → a fix task per affected task (`T-03r`, its owner agent, high-risk, normal flow)
before the milestone card; Minor findings go on the milestone card.

**Milestone end ⏸** (every milestone but the last): task `M<n>-docs` with two steps: **architect** as-built sync of
`docs/LLD.md` (changes since last milestone, section numbers kept stable), then **docs**
README pass. Milestone card (includes the LLD changes): **Approve + continue in a fresh
session (Recommended)** / Approve and continue here / Request changes.
Fresh session → update STATE.md "Next step", `$TASKGIT record <repo> "chore: milestone M<n>"`,
then tell the owner: "Start a new chat and run `/setup-project resume <repo>`", and stop.
**The last milestone** has no docs task and no milestone card: its last approved task leads
straight into the handover (stage 8), whose architect and docs steps cover the same ground.
Each milestone costs a docs task and a session restart, so the planner sizes them to the project.

**Long session check (between tasks).** Your own context grows with every task, and every call
re-reads all of it, so a long session costs more per task the longer it runs. After you
`record` an approved task, if **6 or more tasks** have been approved in this session, no task
is mid-step (every open `TASK_PROGRESS.md` has no ⏳) and the milestone isn't about to end
(its last task isn't next), ask once: **Continue in a fresh session (Recommended)** / Continue
here. Fresh session: the same steps as at milestone end (STATE.md "Next step", `record`, tell
the owner to resume, stop). Continue here: don't ask again until another 6 tasks are approved.
In unattended mode this counts like a milestone: answer Recommended and log `SESSION DONE`.
