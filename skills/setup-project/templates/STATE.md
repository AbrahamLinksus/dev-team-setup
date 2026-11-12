# STATE — {{project}}

> Source of truth for resuming. Updated after every task.

| Field | Value |
|---|---|
| Problem | {{one-line problem}} |
| Repo | {{github_owner}}/{{repo}} ({{private/public}}) |
| Local folder | {{base}}/{{repo}} (worktrees in {{base}}/{{repo}}-wt/; start sessions in {{base}}) |
| Status | {{Active · Paused (reason) · Abandoned (reason) · Complete}} |
| Stage | {{0 Intake · 1 Spec · 2 HLD · 3 Team pick · 4 LLD · 5 Env · 6 Tasks · 7 Build · 8 Handover}} |
| Size | {{small · medium · large}} · signals: {{risk signals present, or none}}: sets milestones, design depth, the task cap, who tests and reviews low-risk tasks |
| Milestone | {{M2 · name}} ({{done}}/{{total}} tasks) |
| Next step | {{T-08 · owner · what}} |
| Started | {{YYYY-MM-DD HH:MM ±HH:MM}} (cost.py --since) · Budget {{USD, 0 = no cap}} |
| Last updated | {{YYYY-MM-DD HH:MM ±HH:MM, the owner's local time}} |

## Team
| Agent | Model | Why on this project |
|---|---|---|

## Open work
- Tasks in progress live on `wip/*` branches (see `taskgit.sh list`); their step states are in each branch's TASK_PROGRESS.md.

## Open decisions (waiting for the owner)
- none

## How to run
```bash
uv sync            # python deps
# npm ci           # frontend deps
# uv run ...       # start commands
```

## Context additions
Context gaps agents reported (`Context gap:` in a REPORT). The Orchestrator adds these to the
`Read:` field for that role on top of the per-role defaults in brief-template.md.
| Role | Also read | Why (from gap report) |
|---|---|---|

## Notes for the next session
- 
