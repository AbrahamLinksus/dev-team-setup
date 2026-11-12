# Approval and cost modes

Read from the plugin config (`approval_mode`, `cost_mode`). The owner can switch for
one project at the team-pick step; record the choice in STATE.md.

## Risk classification (run after review + sync, before any card)

A task is **high-risk** if any of these is true; otherwise it's **low-risk**:
- any goal ⚠️ or ❌
- `scripts/check.sh` needed a debugger round, or the reviewer found anything Major/Critical
- it answered a Tier 1 decision, or added/changed a package
- it touches an API contract, DB schema, auth/security code, data deletion, prompts used in
  production, deployment/CI, or a file listed as a variation point in CONVENTIONS.md
- the scope check reverted any file
- it touches a gate file (`scripts/check.sh`, a lint/type/test config, CI: the `gates` group in
  `scopes.json`): only env-setup and devops may change those, so any such change needs your eyes
- diff over 400 changed lines

Record the class and the reason in TASK_PROGRESS.md.

## approval_mode

**every-task** (default): every task gets its own result card and approval. Independent tasks
keep moving while a card waits (`stage-7-build.md`, "Don't let the team idle").

**batch-low-risk**:
- High-risk tasks: their own card, as usual.
- Low-risk tasks: synced + checked, card prepared, then **queued** (status `Needs you (batch)`);
  the next independent task starts immediately.
- Send one **batch card** when the queue reaches 3 tasks, at milestone end, or when nothing
  else can start. One row per task (goals x/y, checks, one-line change summary), the best
  1–2 visuals per task, then AskUserQuestion (multiSelect): "Approve these" with every task
  pre-listed; anything the owner leaves unticked gets its own full card.
- Approve the ticked tasks one at a time with `$TASKGIT approve` (each one re-syncs and
  re-checks against the main the previous one produced).

**autopilot** (fastest: the owner stops the build only for what needs them):
- **Auto-approved:** a task that is low-risk (above) **and** has every goal ✅ **and** passed `sync`.
  Update TASKS.md, STATE.md and DECISIONS.md in the main checkout, run `$TASKGIT approve` yourself
  straight away (it commits those updates with the task), and start the next task. Then send its
  card as usual, headed `✅ Auto-approved T-07 · Undo?`, with AskUserQuestion: **Keep** (default) /
  **Undo**. Don't wait for the answer: carry on, and handle it whenever it comes.
- **Undo** → `$TASKGIT undo <repo> T-07` (a new commit on main that reverts the task's commit),
  then TASKS.md: the task back to `Backlog` with "undone by the owner", `record` (undo
  leaves the shared files to you). Exit 4 = a later
  task changed the same lines: tell the owner, and offer to undo the later task first or to make
  the change as a new task.
- **Still stops, exactly as in every-task:** any ⚠️/❌ goal, every high-risk task, every Tier 1
  decision card, change requests, milestone cards and the handover card. Tier 1 never shrinks.
- Never auto-approve when a change request is open, the task needed a debugger round, or the
  scope check reverted anything (all three already make it high-risk).

## cost_mode

**quality** (default): agents use the models in their definitions; debugger max 3 rounds.

**balanced**:
- For low-risk-looking tasks (no contract/schema/security/variation-point files in the
  task's planned scope), spawn **reviewer** and **debugger** with `model: "sonnet"`.
  The final classification can still turn it high-risk; then re-review with Opus.
- Debugger max 2 rounds before a decision card.
- Researcher is skipped when the LLD already pins every needed package.

**fast** (quickest wall-clock time; Sonnet writes faster than Opus):
- Spawn with `model: "sonnet"` every agent whose definition says Opus, **except planner and
  architect**: the design everything else follows stays on the strongest model. That covers
  reviewer, debugger, evaluator, explainer and statistician. Haiku and Sonnet agents keep theirs.
- **High-risk tasks still get an Opus reviewer.** Classify before the review when the planned scope
  already makes it high-risk; if the final classification turns a task high-risk after a Sonnet
  review, re-review with Opus before its card.
- Debugger: round 1 on Sonnet; a second round goes to Opus (the cheap model already missed it).
  Max 2 rounds, then a decision card.
- Researcher is skipped when the LLD already pins every needed package.
- Pairs well with `approval_mode: autopilot`, which removes most waits for the owner.

## Build model tip (balanced and fast only)

The build stage mostly dispatches agents, and the Orchestrator is the session's model: about 40%
of a run's cost. Sonnet costs half as much as Opus per token. On the planning card (stage 6) in
`balanced` or `fast`, add one line: "Tip: planning is done; for the build you can switch this
session to Sonnet (`/model sonnet`) to roughly halve its cost. Switch back for a change request."
Say it once, never switch it yourself, and never in `quality`: the session's model is the owner's.

## Things that never batch or downgrade
Tier 1 decision cards, the HLD/LLD/install checkpoints, milestone cards, any reject, and
anything the owner asked to see individually.
