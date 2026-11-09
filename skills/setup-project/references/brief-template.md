# Agent brief template

Fill every field for every spawn. Agents can't find these paths on their own, and they read
**only** what `Read:` lists, so build it carefully: start from the role's default below, add
the task's `Context:` items from TASKS.md, then any row for this role in STATE.md
"Context additions".

```
BRIEF · <task-id> · <agent-name> · <step>
Worktree:     <repo>-wt/<task-id>     (work only here; branch wip/<task-id>)
Task:         <title>
Acceptance criteria (verbatim from TASKS.md):
  - ...
Step:         <implement | test | review | debug round n/3 | rework | ...>
Read:         <exact files and sections, one per line, e.g.>
              docs/LLD.md §2.1, §4
              docs/SPEC.md US-03, US-04
              docs/CONVENTIONS.md
              src/auth/*
              TASK_PROGRESS.md
              <review only> .results/<task-id>/changes.diff
              <debug only>  .results/<task-id>/<failing step>-<agent>.md (failure output) + the changed files
Rework:       <rework only> previous REPORT (verbatim, ≤12 lines) + owner's change request (verbatim)
Write full report to: .results/<task-id>/<step>-<agent>.md
TEAM_RULES:   <plugin root>/skills/setup-project/references/team-rules.md
CAPTURE:      <plugin root>/skills/setup-project/scripts/capture.py
Return:       short REPORT (≤12 lines) or DECISION NEEDED (format in TEAM_RULES)
```

Write files the agent reads before spawning it, e.g. for the reviewer:
`$TASKGIT diff <repo> <task-id> > <worktree>/.results/<task-id>/changes.diff` (don't open it yourself).

## Per-role `Read:` defaults

"The task's LLD sections" and "its SPEC stories" come from the task's `Context:` line.

| Agent | Read |
|---|---|
| backend-coder, frontend-coder, rag-engineer, agent-engineer, prompt-engineer, trainer, modeler, mlops, data-acquisition, data-cleaner, eda, visualizer | the task, its LLD sections, `docs/CONVENTIONS.md` (+ `Context:` files) |
| tester | acceptance criteria, the LLD interface sections (`§n.1`, `§n.2`) for the task |
| reviewer | `.results/<id>/changes.diff`, `docs/CONVENTIONS.md`, the task's LLD sections |
| debugger | the failure output file, the changed files, the task's LLD sections |
| evaluator | acceptance criteria, the metric section of SPEC/HLD, `evals/` files |
| statistician, explainer, insights-reporter | the task, its SPEC stories / HLD success-metrics section, the result files the task names |
| devops | `docs/LLD.md` §0, `docs/CONVENTIONS.md` §6, `scripts/check.sh` |
| env-setup | `docs/LLD.md` §0, `docs/CONVENTIONS.md` §6 (+ `.results/env/plan.md` in phase 2) |
| researcher | the HLD sections / decision points named in the brief |
| git-pr | nothing beyond the brief |
| planner, architect, docs | full docs (they own them) |

When an agent's REPORT has `Context gap: <what and why>`, add a row for that role to
STATE.md "Context additions" (committed with the next `record`) so later briefs include it.
