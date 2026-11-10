# STATE — {{project}}

> Source of truth for resuming. Updated after every task.

| Field | Value |
|---|---|
| Problem | {{one-line problem}} |
| Repo | {{github_owner}}/{{repo}} ({{private/public}}) |
| Local folder | {{base}}/{{repo}} (worktrees in {{base}}/{{repo}}-wt/; start sessions in {{base}}) |
| Stage | {{0 Intake · 1 Spec · 2 HLD · 3 Team pick · 4 LLD · 5 Env · 6 Tasks · 7 Build · 8 Handover}} |
| Milestone | {{M2 · name}} ({{done}}/{{total}} tasks) |
| Next step | {{T-08 · owner · what}} |
| Last updated | {{YYYY-MM-DD HH:MM IST}} |

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
