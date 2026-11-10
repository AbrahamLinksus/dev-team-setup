# Stages 1–6 · Planning (spec → tasks)

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 1 · Spec interview ⏸

Follow `spec-interview.md`: **planner** rounds, each one updating `docs/SPEC.md` and returning
a QUESTIONS block, until it returns SPEC COMPLETE (at most 6 rounds; then open items become
assumptions listed on the spec card). Ask every
round's questions in one AskUserQuestion call (recommended option first, "Decide for me"
where sensible) and send a one-line progress note between rounds.
UI projects: planner writes lo-fi wireframes; render them (mobile + desktop).
Spec card: wireframes + spec summary + every *(assumed)* line → Approve / Request changes /
Answer more questions. Nothing is designed before the spec is approved.

## 2 · High-level breakdown ⏸

**planner** → `docs/HLD.md` from the approved spec (every user story mapped to a module).
Render the data-flow diagram; send it with a ≤10-line summary; Approve / Request changes /
Reject; loop until approved.

## 3 · Team pick ⏸

From the HLD modules and `agent-catalog.md`, propose the build team: a table of module →
agent(s) · model · one-line reason. AskUserQuestion: "Approve this team?" (Approve /
Remove some) plus up to 3 multiSelect questions of optional agents (max 4 each, with
reasons). Mention the approval and cost modes; the owner can type a change.

## 4 · LLD + conventions + packages ⏸

1. **researcher** (unless skipped by cost mode) → `docs/research.md`.
2. **architect** → `docs/LLD.md`, `docs/CONVENTIONS.md`, `.devteam/scopes.json` if the folder
   layout differs from the defaults.
3. Render component/sequence diagrams, package table, layer map.
4. Group the architect's Tier 1 items: real trade-offs → decision cards (max 4 per call);
   forced/obvious choices go in the package table, approved with the LLD. Then Approve
   LLD + conventions + packages / Request changes / Reject. Log answers in DECISIONS.md.

## 5 · Environment setup ⏸

**env-setup** phase 1 → install plan; **Install** / **Edit** (the owner says what to change →
env-setup redoes phase 1) / **Cancel** (nothing is installed: back to the LLD's package table at
stage 4 to pick different packages, or **Pause** the project, see `references/anytime.md`). Phase 2 → install,
`scripts/check.sh` (with `CHECK_NO_COVERAGE=1` for the skeleton), configs, pre-commit, smoke
check with terminal images.

## 6 · Tasks + plan merge ⏸

**planner** → `TASKS.md`. Planning card (spec, HLD, team, LLD, env, task count per milestone).
On approval run `$TASKGIT approve <repo> plan "chore: spec, design, environment and tasks"` yourself.
Mirror the current milestone in the task widget.
