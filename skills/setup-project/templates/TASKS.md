# TASKS — {{project}}

Status: Backlog → In progress → Review → Needs you → Done

A task is one user-visible feature slice end to end (data, logic, UI, tests), never one layer.
Only the first task may be a foundation task (the app starts and shows its first screen; shared
helpers). Caps by size: small 8, medium 15, large 30; an extra task carries `Why separate:`.

Every task needs `Owner:`, `Depends on:` (real data or interface dependencies only, never a
preferred order; `—` for none) and `Files:` (paths or globs it will create or change): the build
schedules from them (`taskgraph.py`), running tasks with no dependency and no shared files at
the same time.

`Context:` lists exactly what the task's agents need to read: spec stories, LLD sections
(by number) and file globs. The Orchestrator builds every brief's `Read:` field from it.

## M1 · {{milestone name}}

### T-01 · {{title}}
- Owner: {{agent}}
- Depends on: —
- Files: {{src/auth/*, tests/test_auth.py}}
- Context: SPEC {{US-03, US-04}} · LLD {{§2.1, §4}} · files: {{src/auth/*}}
- Status: Backlog
- Acceptance criteria:
  - [ ] {{checkable outcome}}
  - [ ] {{checkable outcome from a usage scenario}} (S-01)
- Result: {{filled at approval: ✅/⚠️ summary · ≈$cost · role shares (`cost.py --result`); the commit carries a `Task: T-01` trailer}}
