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

## cost_mode

**quality** (default): agents use the models in their definitions; debugger max 3 rounds.

**balanced**:
- For low-risk-looking tasks (no contract/schema/security/variation-point files in the
  task's planned scope), spawn **reviewer** and **debugger** with `model: "sonnet"`.
  The final classification can still turn it high-risk; then re-review with Opus.
- Debugger max 2 rounds before a decision card.
- Researcher is skipped when the LLD already pins every needed package.

## Things that never batch or downgrade
Tier 1 decision cards, the HLD/LLD/install checkpoints, milestone cards, any reject, and
anything the owner asked to see individually.
