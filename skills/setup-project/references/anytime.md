# Anytime · change requests, pause, abandon

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## Change requests (anytime)

When the owner changes **what** is built or **how** it's designed (not a fix to one task),
follow `change-requests.md`: pause new tasks and hold approvals → `CR-<n>` branch → planner/architect update
SPEC/HLD/LLD → "what changes" card ⏸ → planner re-plans TASKS.md → merge
(`$TASKGIT approve <repo> CR-<n> "docs: CR-<n> …"`) → sync affected task branches → offer
**Continue in a fresh session (Recommended)** / Continue here (fresh session: same steps as at
milestone end) → resume.
Design docs change only through this flow, the milestone as-built sync, or handover.

## Pause or abandon (anytime)

The owner can say "pause" or "stop" at any card, or pick it from an AskUserQuestion.
- **Pause**: finish nothing new; checkpoint every open `wip/*` branch (they're already pushed),
  set STATE.md `Status: Paused` with the reason and the next step, `$TASKGIT record`, stop any
  server you started. `/setup-project resume <repo>` later continues from STATE.md as usual.
- **Abandon**: ask once to confirm (it can't be resumed). Then `$TASKGIT reject` every open task
  branch, set STATE.md `Status: Abandoned` with the reason, `$TASKGIT record`. The repo and
  everything already on main stay; nothing is deleted on GitHub.
