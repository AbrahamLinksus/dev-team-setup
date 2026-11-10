# Stage 7 · Build loop

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 7 · Build loop

Take every `Backlog` task whose dependencies are `Done`; run independent tasks in parallel
(own worktrees; shared files are only edited on main). Per task `T-xx`:

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
4. `$TASKGIT sync <repo> T-xx`. Exit 4 (conflict) / 5 (checks fail; output path in the error)
   → debugger, back to step 3.
5. Classify risk (`approval-modes.md`); produce visuals (`visual-capture.md`, screenshots first).
6. Result card now or queued for a batch, per approval mode. Then:
   - **Approve** → run `$TASKGIT approve <repo> T-xx "<msg>"` yourself, with a conventional-commit
     message built from the card (`feat(auth): add login endpoint [T-07]`); then update `TASKS.md`,
     `DECISIONS.md`, `STATE.md` in the main checkout and `$TASKGIT record <repo> "chore: record T-xx"`.
   - **Request changes** that stays within the task's acceptance criteria → back to step 2,
     continuing the owner agent (see **Rework continuation** in SKILL.md). Anything wider is a
     **change request** (`references/anytime.md`).
   - **Reject** → run `$TASKGIT reject <repo> T-xx` yourself; Backlog + reason; `record`.
   - approve exits non-zero: 4/5 → debugger, then a new card; 7 → report the push problem;
     8 → a change request is open: keep the card queued until it merges.

**Milestone end ⏸**: task `M<n>-docs` with two steps: **architect** as-built sync of
`docs/LLD.md` (changes since last milestone, section numbers kept stable), then **docs**
README pass. Milestone card (includes the LLD changes): **Approve + continue in a fresh
session (Recommended)** / Approve and continue here / Request changes.
Fresh session → update STATE.md "Next step", `$TASKGIT record <repo> "chore: milestone M<n>"`,
then tell the owner: "Start a new chat and run `/setup-project resume <repo>`", and stop.

**Long session check (between tasks).** Your own context grows with every task, and every call
re-reads all of it, so a long session costs more per task the longer it runs. After you
`record` an approved task, if **6 or more tasks** have been approved in this session, no task
is mid-step (every open `TASK_PROGRESS.md` has no ⏳) and the milestone isn't about to end
(its last task isn't next), ask once: **Continue in a fresh session (Recommended)** / Continue
here. Fresh session: the same steps as at milestone end (STATE.md "Next step", `record`, tell
the owner to resume, stop). Continue here: don't ask again until another 6 tasks are approved.
In unattended mode this counts like a milestone: answer Recommended and log `SESSION DONE`.
