# Stages 1–6 · Planning (spec → tasks)

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 1 · Spec interview ⏸

Follow `spec-interview.md`: **planner** rounds, each one updating `docs/SPEC.md` and returning
a QUESTIONS block, until it returns SPEC COMPLETE (at most 6 rounds; then open items become
assumptions listed on the spec card). Ask every
round's questions in one AskUserQuestion call (recommended option first, "Decide for me"
where sensible) and send a one-line progress note between rounds.
**product-critic** then stress-tests the spec with usage scenarios; its high gaps are asked on
the spec card (`spec-interview.md`, Spec critic).
UI projects: planner writes lo-fi wireframes; render them (mobile + desktop).
Spec card: wireframes + spec summary + every *(assumed)* line → Approve / Request changes /
Answer more questions. Nothing is designed before the spec is approved.
**Project size.** The planner sizes by **risk signals**, not by a guessed task count: backend,
auth, database, multi-user, external services/payments, AI/ML, deployment. 0–1 signals = small,
2–3 = medium, 4+ = large; more than 15 user stories bumps it up one size. A signal counts only
for its real risk: a server only this computer or the home network reaches, SQLite or files, one
household, and running at home count as **none** (planner duty in `agents/planner.md`). Its `Size:` line (size,
the signals present, the story count) goes on the spec card, in plain words ("small: no accounts,
no server, nothing deployed"), and into STATE.md "Size". It sets how much process the build gets:
milestones, design depth, the task cap, and who tests and reviews low-risk tasks.
High-risk tasks always get the full team. It changes only when a signal is added or removed (a change request, or
the design adds a server); the owner can change it on any planning card.
**Design path** (decided at the spec card, recorded in STATE.md "Design"). A separate system design
(stage 2 HLD → 3 team pick → 4 LLD, three cards) pays off only when there is real interaction to
agree on first: the size is **large**, or the planner's `Parts:` line names **2 or more parts that
run separately** (an API and a web app, a background worker, a mobile app), or the **external
services/payments** signal is counted. **Every other project takes the one design step below**:
no `docs/HLD.md`, one design card. Say which path on the spec card, in one line ("one design
step: it's one app with no outside services").
**Small idea?** When the size is **small** (or the spec has at most 5 user stories) and there is no
AI/ML or data-science work, it is also the **quick track**: split Approve into **Approve · quick
track (Recommended)** / **Approve · full track**, saying in one line what quick track skips. Record
the track in STATE.md.

## Quick track and the one design step (most projects)

Same guardrails, checkpoints and per-task cards; fewer planning stops. Replaces stages 2–4:
- **One design step:** the **architect** writes `docs/LLD.md`, starting with **§0.0 Big picture**
  (the modules, the user stories each one serves, the data-flow diagram, the milestones), and
  `docs/CONVENTIONS.md`, in one go, **short**: the big picture about one screen, the rest only the
  sections the tasks will read (the brief says "one design step: keep it short"). No `docs/HLD.md`:
  the big picture is the high-level design. The **researcher** runs only if a needed package isn't
  pinned by the spec's stack.
- **The team** comes from the big picture's modules, with their catalog models (never a bigger one
  unless the owner picks it on the design card). Quick track: the default team, no questions (the
  coders the modules need, plus tester, reviewer, debugger and docs). Otherwise: the team table as
  at stage 3, with its optional-agent questions on the design card.
- **One design card ⏸:** the data-flow diagram, the team, the package table and every Tier 1 item
  from the architect → Approve design / Request changes. Still on the default `quality` cost mode →
  the same **Cost mode** question as the team-pick card, Balanced first. Real trade-offs still get
  their own decision cards (Tier 1 never shrinks).
- Stage 5 (install) is unchanged: installing is Tier 1.
- **Stage 6** takes the milestones from §0.0. Quick track only: one milestone, and approval mode
  **batch-low-risk** unless the owner picks every-task on the design card (record it in STATE.md).
- The owner can switch to the separate system design at any card ("let's do this properly"):
  carry on from stage 2, with the planner turning §0.0 into `docs/HLD.md`.

## 2 · High-level breakdown ⏸ (separate system design only)

Copy `templates/HLD.md` to `docs/`. **planner** → `docs/HLD.md` from the approved spec: the parts
and how they talk, every user story mapped to a module.
Render the data-flow diagram; send it with a ≤10-line summary; Approve / Request changes /
Reject; loop until approved.

## 3 · Team pick ⏸

From the HLD modules and `agent-catalog.md`, propose the build team: a table of module →
agent(s) · model · one-line reason. **Models are the catalog's**: never move an agent to a bigger
model on your own (an Opus coder costs about twice a Sonnet one). If you think a role needs one,
offer it as an option on the card with its cost, and record the owner's answer in DECISIONS.md. AskUserQuestion: "Approve this team?" (Approve /
Remove some) plus up to 3 multiSelect questions of optional agents (max 4 each, with
reasons). Mention the approval and cost modes; the owner can type a change.
**Small and medium projects still on the default `quality`:** add a question **Cost mode** with
**Balanced (Recommended)**: "design stays on the strongest model; reviews and fixes of low-risk
tasks use a faster, cheaper one" / Quality / Fast. Record the answer in STATE.md; it applies from
this card on. (The home-cookbook run stayed on quality: every review and fix ran on Opus.)

## 4 · LLD + conventions + packages ⏸

1. **researcher** (unless skipped by cost mode) → `docs/research.md`.
2. **architect** → `docs/LLD.md`, `docs/CONVENTIONS.md`, `.devteam/scopes.json` if the folder
   layout differs from the defaults.
3. Render component/sequence diagrams, package table, layer map.
4. Group the architect's Tier 1 items: real trade-offs → decision cards (max 4 per call);
   forced/obvious choices go in the package table, approved with the LLD.
   **Standard toolkit card** (separate system design in builder mode; on the one design step the
   design card's package table groups the same items as one "standard toolkit" line): the items the architect marked `toolkit` (linters,
   formatter, type checker, test runner, coverage, version pins) come as **one** card: what the
   toolkit does for the owner in one line ("checks every change for mistakes before you see it"),
   the list on a collapsed `Technical detail:` line, then **Approve toolkit** / **Show me each**
   (each item as its own decision card). Items marked `trade-off` (database, framework, hosting,
   anything paid or external, anything whose "If wrong" is more than a day) keep their own cards:
   Tier 1 still reaches the owner, it just arrives as one decision where one is enough. Then Approve
   LLD + conventions + packages / Request changes / Reject. Log answers in DECISIONS.md.

## 5 · Environment setup ⏸

**env-setup** phase 1 → install plan; **Install** / **Edit** (the owner says what to change →
env-setup redoes phase 1) / **Cancel** (nothing is installed: back to the LLD's package table at
stage 4 to pick different packages, or **Pause** the project, see `references/anytime.md`). Phase 2 → install,
`scripts/check.sh` (with `CHECK_NO_COVERAGE=1` for the skeleton), configs, pre-commit, smoke
check with terminal images.

## 6 · Tasks + plan merge ⏸

**planner** → `TASKS.md`: one task per user-visible feature slice, plus at most one foundation task.
Check it with `python3 $TASKGRAPH <wt>/TASKS.md --size <STATE.md Size>`: exit 2 (a cycle, an unknown
ID, a task missing `Owner`, `Depends on` or `Files`) → back to the planner with the error line.
**A feature task claiming frozen code is never accepted**: the planner moves that piece into the
foundation (or a shared-change task) and narrows `Frozen:` to the shared files. **Any other warning sends the plan back once** (over the task cap or milestone limit, or a parallel factor
under 1.5 with 4+ tasks): the planner merges tasks and milestones, and for files shared by 3+
tasks the **architect** splits them per feature in the LLD first, then the planner re-plans. A
warning that survives the second plan goes on the planning card with the planner's reason.
**The task graph goes on the planning card:** `python3 $TASKGRAPH <wt>/TASKS.md --mermaid >
<wt>/.results/plan/tasks.mmd`, then `python3 $CAPTURE mermaid <wt>/.results/plan/tasks.mmd
<wt>/.results/plan/tasks.png` (the critical path is highlighted), and the `--summary` lines under
it, which every owner can read ("Round 2: 3 features at the same time"). A parallel factor under
1.5 with 4+ tasks prints a warning: the card says why (or the planner moves shared helpers into
the foundation task).
Planning card (spec, the design, team, env, task graph, task count per milestone, project size, and
`Scenarios covered: <n>/<n>`: each scenario in `docs/scenarios.md` tagged on some criterion, and
`Production gate: <n> items, <n> N/A`: every applicable item of `docs/PRODUCTION.md` tagged on a
criterion). The planner's brief gives it the `templates/PRODUCTION.md` path. Show the task
count against the size's cap (**small 8, medium 15, large 30**); over the cap, list each extra
task's `Why separate:` line so the owner can ask to merge them.
In `balanced` or `fast` cost mode, add the build-model tip (`approval-modes.md`).
On approval run `$TASKGIT approve <repo> plan "chore: spec, design, environment and tasks"` yourself.
Mirror the current milestone in the task widget.
