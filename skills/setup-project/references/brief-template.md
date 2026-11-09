# Agent brief template

Fill every field for every spawn. Agents can't find these paths on their own.

```
BRIEF · <task-id> · <agent-name>
Worktree:     <repo>-wt/<task-id>     (work only here; branch wip/<task-id>)
Task:         <title>
Acceptance criteria (verbatim from TASKS.md):
  - ...
Step:         <implement | test | review | debug round n/3 | ...>
Inputs:       docs/HLD.md · docs/LLD.md · docs/CONVENTIONS.md · TASK_PROGRESS.md
              <review only> Diff to review: .results/<task-id>/changes.diff
              <debug only>  Failure output: .results/<task-id>/failure.txt
              <rework only> Owner's change request: "<verbatim>"
TEAM_RULES:   <plugin root>/skills/setup-project/references/team-rules.md
CAPTURE:      <plugin root>/skills/setup-project/scripts/capture.py
Return:       REPORT or DECISION NEEDED (format in TEAM_RULES)
```

For the reviewer, write the diff first:
`$TASKGIT diff <repo> <task-id> > <worktree>/.results/<task-id>/changes.diff`
