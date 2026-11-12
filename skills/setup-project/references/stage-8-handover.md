# Stage 8 · Handover

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 8 · Handover ⏸

Task `handover` (normal task flow, after the last milestone). It starts with the **batched
review** of the last milestone's tasks when any had theirs batched (`stage-7-build.md`).
0. **Fix, don't list.** Every row of STATE.md "Known minors" sized ≈5 min or less is fixed now,
   in the handover worktree, by its owner agent (one step per agent, the rows in its brief), then
   removed from the list. Larger ones stay and go on the handover card.
0b. **Screenshots for the docs.** `.results/` is git-ignored and each task's copy is deleted when it
   is approved, so a README can never link into it. The **tester** starts the app in the handover
   worktree and captures it fresh (`$CAPTURE web <url> <wt>/.results/handover/app --mobile`, plus
   a `$CAPTURE term` of the test run), then stops it. You copy the 2–4 best PNGs to
   `<wt>/docs/images/` (tracked) and list those paths in the docs agent's `Read:`.
1. **devops**: CI running `scripts/check.sh` on push/PR (deploy only if the owner asks).
2. **architect**: as-built sync of `docs/LLD.md` (changes since the last milestone), then
   `docs/ARCHITECTURE.md` (as built) and `docs/WALKTHROUGH.md` (templates).
3. **docs**: README "How to run / How to test / How to extend" with the screenshots in `docs/images/`,
   and `OWNER.md` (one screen for the owner, from `templates/OWNER.md`: what it does, how to start
   it, what it can't do, what could lose data, what to do when something breaks, running costs).
4. **reviewer** (read-only): checks that every path and function named in the three docs exists.
   **tester** (it has Bash): runs every command in the README's "How to run" and "How to test"
   in a fresh clone of the handover branch, each under `timeout`, captures the run with
   `$CAPTURE term`, and reports any command that fails or doesn't exist.
5. **Production gate.** The reviewer also fills a `## Production gate` table in its full report:
   each applicable item of `docs/PRODUCTION.md` with its status, `Built + tested (<the test or
   capture that proves it>)` only when that proof exists and passed in the tester's run, else
   `Open`. Then **docs** writes those statuses into `docs/PRODUCTION.md`.
Handover card (`result-card.md`) → Approve handover / Request changes. **Approve is offered only
when no gate item is Open.** Each open item instead gets, in the same AskUserQuestion call (max 4
per call): **Build it** (a fix task, normal flow, then the gate is re-checked) / **Waive it** (a
Tier 1 decision: the card states the consequence, e.g. "anyone with the link can read every
recipe", logged in DECISIONS.md and written to the item as `Waived by the owner (D-xx: …)`).
**Known minors left** (larger than ≈5 min) go on the card the same way: **Fix it** / **Waive it**
(logged in DECISIONS.md). The handover never ships an unwaived "known minor".
Then STATE.md → "Complete" and a final `record`.
