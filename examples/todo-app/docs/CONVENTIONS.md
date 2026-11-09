# CONVENTIONS — todo-app

> Written by the Architect with the LLD and approved by the owner. Every coder reads this
> before every task; the Tester enforces section 6 automatically, and the Reviewer
> enforces sections 2–5.

## 1. Stack-specific style
- Python: PEP 8 via ruff; type hints on every public function; Pydantic models at every I/O boundary.
- TypeScript: strict mode; no `any`; named exports; React function components + hooks.
- Python 3.13, src layout (`backend/src/todo_app`), absolute imports only; ruff line length 100.
- Domain objects are frozen `@dataclass`es; Pydantic models live only in `api/schemas.py` and `config.py`.
- SQL lives only in `SqliteTodoRepository`, always parameterised (`?` placeholders), one connection per call.
- Frontend: Prettier defaults + `singleQuote: true`; files `PascalCase.tsx` for components, `camelCase.ts` otherwise.
- Components are presentational (props in, callbacks out); only `useTodos` holds state; only `api/` calls `fetch`.
- JSON over the wire is snake_case; `httpTodoApi.ts` is the only place that maps it to camelCase TS types.

## 2. Layering (dependencies point inward only)
```
main.py   →  api/routes  →  services  →  repositories  →  domain
(compose)    (HTTP only)    (business    (SQLite; all     (dataclasses +
                             rules)       I/O here)        errors, no I/O)
```
- Routes never import repositories or `sqlite3`; they get `TodoService` via `Depends(get_todo_service)`.
- Services and domain never import `fastapi`, `starlette`, `sqlite3` or `todo_app.config`.
- Domain/models import nothing from the other layers.
- Only `main.py` constructs `Settings`, `SqliteTodoRepository` and `TodoService`.
- Frontend: `main.tsx (compose) → App.tsx (page) → components → hooks → api`. Components never import hooks or
  `api/httpTodoApi`; hooks never import components; `api/` imports nothing from UI; only `main.tsx` imports `httpTodoApi`.
- Enforced by the import-linter and dependency-cruiser contracts written in `docs/LLD.md` § Layer enforcement.

## 3. SOLID: what it means in this project

| Principle | Rule here |
|---|---|
| **S**ingle responsibility | One reason to change per class/module. No I/O mixed with business logic. Services named by capability (`IngestionService`), not `Manager`/`Utils`. |
| **O**pen/closed | Variation points listed in the LLD get an interface (Protocol/ABC); new providers are new classes, never new `elif` branches. |
| **L**iskov substitution | Implementations honour the interface: same input acceptance, same return types, no `NotImplementedError` stubs. |
| **I**nterface segregation | Small interfaces per client need; split any interface where clients use only part of it. |
| **D**ependency inversion | Services receive dependencies via constructor or framework injection (`Depends`); they never construct DB/HTTP/LLM clients themselves. Wiring happens in one composition root (`app/container.py` or `main.py`). |

**Where to abstract** (and where not): abstractions are required for external services
(DB, LLM, embeddings, vector store, third-party APIs) and the variation points named in
the LLD. Elsewhere, plain functions and concrete classes are fine. Don't add an interface
with a single implementation and no planned second one.

**Variation points in this project (the only interfaces):**
| Interface | Real implementation | Second implementation |
|---|---|---|
| `TodoRepository` (Protocol, `repositories/base.py`) | `SqliteTodoRepository` | `InMemoryTodoRepository` in `tests/fakes.py` |
| `TodoApi` (TS interface, `api/types.ts`) | `createHttpTodoApi(baseUrl, fetchFn)` | in-test fake object for hook/component tests |

Composition roots: `backend/src/todo_app/main.py::create_app` and `frontend/src/main.tsx`.

## 4. Limits
- Function ≤ 40 lines; cyclomatic complexity ≤ 10; parameters ≤ 5 (use a dataclass/model beyond that).
- File ≤ 300 lines; class ≤ 200 lines.
- No commented-out code, no `print` debugging (use the logger), no TODOs without a task ID.

## 5. Errors, logging, config, tests
- Errors: custom exception types per domain; map them to HTTP errors only in the route layer.
- Logging: structured (key=value or JSON), no secrets or personal data in logs.
- Config: all settings from env via a typed settings object (backend `config.Settings`, pydantic-settings, prefix `TODO_`;
  frontend `src/config.ts` reading `import.meta.env` with a typed default, no zod for one variable); no magic constants
  (the 200-char title limit is a named constant `MAX_TITLE_LENGTH` in `services/todo_service.py`).
- Tests: Arrange-Act-Assert, one behaviour per test, names `test_<unit>_<condition>_<expected>`;
  external services faked through their interfaces, never patched deep inside code.

## 6. Automated checks (`scripts/check.sh` must pass; Tester runs it on every task)

| Check | Python | TypeScript |
|---|---|---|
| Lint + format | `ruff check` + `ruff format --check` (rules: E,F,W,I,N,UP,B,SIM,C90,PL,RUF) | `eslint` (typescript-eslint strict) + `prettier --check` |
| Types | `mypy --strict` (or pyright strict) | `tsc --noEmit` (strict) |
| Complexity / size | ruff `C901` (max 10), `PLR0913` (max 5 args), `PLR0915`; `radon cc -n C` | eslint `complexity: 10`, `max-lines-per-function: 40`, `max-params: 5` |
| Layer rules | `lint-imports` (import-linter contracts for section 2) | `depcruise` (dependency-cruiser rules for section 2) |
| Tests + coverage | `pytest --cov=todo_app --cov-fail-under=85` | `vitest run --coverage` (thresholds 85 for lines, branches, functions, statements; `main.tsx` excluded) |

**Coverage threshold: 85%** on both halves (Tier 1, approved as D-04).

**`scripts/check.sh`** (repo root, `set -euo pipefail`, exits non-zero on the first failure) runs, in order:
```bash
# backend
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src tests
uv run lint-imports
test -z "$(uv run radon cc -n C src)"          # radon exits 0 even when it reports; fail on any C+ block
uv run pytest --cov=todo_app --cov-report=term-missing --cov-fail-under=85
# frontend
cd ../frontend
npx eslint .
npx prettier --check .
npx tsc --noEmit -p tsconfig.json
npx depcruise src --config .dependency-cruiser.cjs
npx vitest run --coverage
```
Tests use a temp SQLite file (`tmp_path`) and never the real `todo.db`; no servers are started by `check.sh`.
