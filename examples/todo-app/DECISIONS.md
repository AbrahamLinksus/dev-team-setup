# DECISIONS — todo-app

## Tier 1 — decided by the owner
| ID | Date | Decision | Chosen | Alternatives | Task |
|---|---|---|---|---|---|
| D-01 | 2026-11-09 | Backend DB access | stdlib sqlite3 behind TodoRepository Protocol | SQLModel | plan |
| D-02 | 2026-11-09 | Frontend data layer | fetch + useState hook | axios + TanStack Query | plan |
| D-03 | 2026-11-09 | TypeScript version | 6.0.3 (typescript-eslint compat) | 7.0.2 + Biome | plan |
| D-04 | 2026-11-09 | Coverage threshold | 85% both halves | 80%, 90% | plan |
| D-05 | 2026-11-09 | LLD, conventions, package table | Approved as written | — | plan |

## Tier 2 — decided by agents (overrule any time)
| ID | Date | Decision | Chosen | Agent | Task |
|---|---|---|---|---|---|
| A-01 | 2026-11-09 | HLD milestone count | 1 milestone (dry run) | planner | plan |
| A-02 | 2026-11-09 | Health endpoint | GET /api/health for smoke checks | architect | plan |
| A-03 | 2026-11-09 | Wire format | snake_case JSON, mapped to camelCase only in httpTodoApi.ts | architect | plan |
| A-04 | 2026-11-09 | Schema creation | init_schema() at startup, no migration tool | architect | plan |
