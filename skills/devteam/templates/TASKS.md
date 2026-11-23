# TASKS — {{project}}

Status: Backlog → In progress → Review → Needs you → Done

A task is one user-visible feature slice end to end (data, logic, UI, tests), never one layer.
Only the first task may be a foundation task (the app starts and shows its first screen; shared
helpers). Caps by size: small 8, medium 15, large 30; an extra task carries `Why separate:`.

Every task needs `Owner:`, `Depends on:` (real data or interface dependencies only, never a
preferred order; `—` for none) and `Files:` (paths or globs it will create or change): the build
schedules from them (`taskgraph.py`), running tasks with no dependency and no shared files at
the same time.

`Files:` is the task's **claim**: while it runs, no other task's agent may write those paths (the
scope guard enforces it). `Frozen:` lists the shared code the foundation builds; after it, only a
task that claims a frozen path itself may change it. Work that touches every feature is one
wire-up task at the end, not an edit inside each feature.

Frozen: {{shared files from the LLD's "Frozen after the foundation" list, e.g. src/core/*, web/templates/base.html, tests/conftest.py}}

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
