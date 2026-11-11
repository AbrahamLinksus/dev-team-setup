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
**Project size.** The planner's `Size:` line (small ≤6 tasks, medium 7–20, large >20) goes on the
spec card and into STATE.md "Size". It sets how much process the build gets: milestones, design
depth, and who tests and reviews low-risk tasks. High-risk tasks always get the full team. At
stage 6, update it from the real task count; the owner can change it on the planning card.
**Small idea?** When the size is **small** (or the spec has at most 5 user stories) and there is no
AI/ML or data-science work,
split Approve into **Approve · quick track (Recommended)** / **Approve · full track**, saying in
one line what quick track skips. Record the track in STATE.md.

## Quick track (small ideas)

Same guardrails, checkpoints and per-task cards; fewer planning stops. Replaces stages 2–4 and
trims 6:
- **One design step:** the **architect** writes `docs/HLD.md` (short: modules and data flow) and
  `docs/LLD.md` + `docs/CONVENTIONS.md` in one go, **short**: HLD about one screen, LLD only the
  sections the tasks will read (the brief says "quick track: keep it short"). The **researcher**
  runs only if a needed package isn't pinned by the spec's stack.
- **Default team, no team-pick card:** the coders the HLD's modules need (backend-coder and/or
  frontend-coder), plus tester, reviewer, debugger and docs, with their catalog models.
- **One design card ⏸:** the data-flow diagram, the team line, the package table and every
  Tier 1 item from the architect → Approve design / Request changes. Real trade-offs still get
  their own decision cards (Tier 1 never shrinks).
- Stage 5 (install) is unchanged: installing is Tier 1.
- **Stage 6:** one milestone. Approval mode for this project is **batch-low-risk** unless the
  owner picks every-task on the design card (record it in STATE.md).
- The owner can switch to the full track at any card ("let's do this properly"): carry on from
  stage 3 with the docs written so far.

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

**planner** → `TASKS.md`. Planning card (spec, HLD, team, LLD, env, task count per milestone, project size).
When the real task count puts the project in another size, update STATE.md "Size" and say so on the card.
On approval run `$TASKGIT approve <repo> plan "chore: spec, design, environment and tasks"` yourself.
Mirror the current milestone in the task widget.
