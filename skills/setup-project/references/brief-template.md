# Agent brief template

Fill every field for every spawn. Agents can't find these paths on their own, and they read
**only** what `Read:` lists, so build it carefully: start from the role's default below, add
the task's `Context:` items from TASKS.md, then any row for this role in STATE.md
"Context additions".

**Every path in a brief is absolute.** A subagent starts in the session's folder, not in the
task's worktree: a relative `docs/LLD.md` would read main's stale copy, and a relative
`.results/…` would write into the main checkout. Below, `<wt>` stands for the worktree's
absolute path (what `$TASKGIT start` printed, e.g. `/home/me/projects/todo-wt/T-03`).

**Order matters for cost.** The model caches a prompt by its longest identical opening, so the
lines that are the same in every brief come first, in this exact order and wording, and
everything task-specific comes after the `BRIEF ·` line. Never move a task-specific value
above it.

```
TEAM_RULES:   <plugin root>/skills/setup-project/references/team-rules.md
CAPTURE:      <plugin root>/skills/setup-project/scripts/capture.py
Return:       short REPORT (≤12 lines) or DECISION NEEDED (format in TEAM_RULES)
BRIEF · <task-id> · <agent-name> · <step>
Worktree:     <wt>     (absolute; work only here; branch wip/<task-id>; every Bash call starts with `cd <wt> &&`)
Task:         <title>
Acceptance criteria (verbatim from TASKS.md):
  - ...
Step:         <implement | test | review | debug round n/3 | rework | ...>
Read:         <exact files and sections, one per line, e.g.>
              <wt>/docs/LLD.md §2.1, §4
              <wt>/docs/SPEC.md US-03, US-04
              <wt>/docs/CONVENTIONS.md
              <wt>/src/auth/*
              <wt>/TASK_PROGRESS.md
              <review only> <wt>/.results/<task-id>/changes.diff
              <debug only>  <wt>/.results/<task-id>/<failing step>-<agent>.md (failure output) + the changed files
Rework:       <rework only> previous REPORT (verbatim, ≤12 lines) + owner's change request (verbatim)
Write full report to: <wt>/.results/<task-id>/<step>-<agent>.md   (only when TEAM_RULES' Output rule 1 applies; add ` · always` to require one)
Port:         <8000 + task number, e.g. T-07 → 8007>     (servers this step starts listen here; second server: 9000 + n)
```

Write files the agent reads before spawning it, e.g. for the reviewer:
`$TASKGIT diff <repo> <task-id> > <wt>/.results/<task-id>/changes.diff` (don't open it yourself).

## Per-role `Read:` defaults

"The task's LLD sections" and "its SPEC stories" come from the task's `Context:` line.
The paths below are relative to the worktree: write them into the brief as `<wt>/<path>`.

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
