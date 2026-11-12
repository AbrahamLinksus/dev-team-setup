# TASKS — {{project}}

Status: Backlog → In progress → Review → Needs you → Done

A task is one user-visible feature slice end to end (data, logic, UI, tests), never one layer.
Only the first task may be a foundation task (the app starts and shows its first screen; shared
helpers). Caps by size: small 8, medium 15, large 30; an extra task carries `Why separate:`.

`Context:` lists exactly what the task's agents need to read: spec stories, LLD sections
(by number) and file globs. The Orchestrator builds every brief's `Read:` field from it.

## M1 · {{milestone name}}

### T-01 · {{title}}
- Owner: {{agent}}
- Depends on: —
- Context: SPEC {{US-03, US-04}} · LLD {{§2.1, §4}} · files: {{src/auth/*}}
- Status: Backlog
- Acceptance criteria:
  - [ ] {{checkable outcome}}
  - [ ] {{checkable outcome}}
- Result: {{filled at approval: ✅/⚠️ summary (the commit carries a `Task: T-01` trailer)}}
