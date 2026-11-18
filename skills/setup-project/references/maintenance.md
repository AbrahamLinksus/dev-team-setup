# After handover · fixes and new features

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

For a project whose STATE.md says `Status: Complete`. Find it first: the folder this session runs in,
or the repo the owner names; with neither, ask which project (never treat the words as a new idea).
Rebuild context exactly as in `resume.md`
steps 1–2 (folder, STATE.md, TASKS.md, DECISIONS.md), then read `OWNER.md` and STATE.md "Owner
mode". Keep the owner's words verbatim in every brief.

## `/setup-project fix <what happened, in plain words>`

A bug report. One task, `FIX-<n>` (next free number), in the normal task flow and approval mode:

1. **Is it a fix?** If the words ask for something the app was never meant to do (a new story, a
   changed non-goal), it's a feature: say so in one line and go to **New feature** below.
   Unsure → ask: "Is this something that used to work / should work, or something new?"
2. **Ask only what's missing** to reproduce it, at most 2 questions in one AskUserQuestion call,
   in plain words ("Which screen were you on?", "What did you expect to see?"). Skip when the
   report already says what, where and what was expected.
3. `$TASKGIT start <repo> FIX-<n>`; TASK_PROGRESS.md with the report verbatim. The task is
   high-risk (separate tester and reviewer) whatever the size.
4. **Reproduce first: tester.** Brief: the owner's words, the matching SPEC stories and flows,
   `Read:` the LLD sections for the module. It writes a test that **fails because of the bug**,
   named `test_fix<n>_…`, and runs it to show the failure. It can't reproduce it → no code
   changes: a card says what was tried and asks the owner for one more detail (or to close it).
5. **Fix: debugger.** `Read:` the failing test and its output. Minimal fix until the new test and
   `scripts/check.sh` pass; a fix that needs a design change returns `DECISION NEEDED`.
6. **review** (reviewer, in parallel with the tester re-running `check.sh`, as in stage 7 step 3).
7. **docs**, only if behaviour the README or `OWNER.md` describes changed.
8. **Card** in the owner's words: "Fixed: <what happened>", what caused it in one plain line, the
   new test's name, and **Try this** (the steps that used to fail). Approve → approve with
   `fix(<module>): <what> [FIX-<n>]`, and add a row to TASKS.md under `## Fixes after handover`.
   STATE.md stays `Complete`.

## New feature on a finished project

`/setup-project add <feature>`, or a fix that turned out to be a feature. Reuse the change-request
flow (`change-requests.md`) with these differences:
- Set STATE.md `Status: Active` and `Stage: 7 Build` first; it goes back to `Complete` after the
  new handover.
- In step 3, the planner also gives a **fresh size estimate for the change alone** from its risk
  signals (a new external service or accounts often move a small project to medium), and the
  "What changes" card shows it. The change's tasks follow that size's rules (task cap, review,
  milestones) and get their own milestone `M<n+1> · <feature>`.
- The new milestone's tasks run in the normal build loop, then a short **handover** for what
  changed: as-built sync, README and `OWNER.md`, the production gate for the new items, handover
  lint. The handover card lists only what changed.
