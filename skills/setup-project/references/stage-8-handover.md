# Stage 8 · Handover

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 8 · Handover ⏸

Task `handover` (normal task flow, after the last milestone):
0. **Screenshots for the docs.** `.results/` is git-ignored and each task's copy is deleted when it
   is approved, so a README can never link into it. The **tester** starts the app in the handover
   worktree and captures it fresh (`$CAPTURE web <url> <wt>/.results/handover/app --mobile`, plus
   a `$CAPTURE term` of the test run), then stops it. You copy the 2–4 best PNGs to
   `<wt>/docs/images/` (tracked) and list those paths in the docs agent's `Read:`.
1. **devops**: CI running `scripts/check.sh` on push/PR (deploy only if the owner asks).
2. **architect**: `docs/ARCHITECTURE.md` (as built) and `docs/WALKTHROUGH.md` (templates).
3. **docs**: README "How to run / How to test / How to extend" with the screenshots in `docs/images/`.
4. **reviewer** (read-only): checks that every path and function named in the three docs exists.
   **tester** (it has Bash): runs every command in the README's "How to run" and "How to test"
   in a fresh clone of the handover branch, each under `timeout`, captures the run with
   `$CAPTURE term`, and reports any command that fails or doesn't exist.
Handover card (`result-card.md`) → Approve handover / Request changes. Then STATE.md →
"Complete" and a final `record`.
