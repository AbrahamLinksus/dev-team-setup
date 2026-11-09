# Production benchmark: team issue tracker

A multi-user issue tracker: an API with accounts, permissions and pagination, plus a small
web UI, packaged like a real service (Docker, CI, migrations, logging).

## API contract

All bodies are JSON. Every endpoint except `/health`, `/auth/register` and `/auth/login`
needs `Authorization: Bearer <token>`; missing or invalid token → `401`.

### Health
| Request | Response |
|---|---|
| `GET /health` | `200 {"status": "ok"}` |

### Accounts
| Request | Response |
|---|---|
| `POST /auth/register {"email", "password"}` | `201 {"id", "email"}` · email already used → `409` · invalid email or password under 8 characters → `422` |
| `POST /auth/login {"email", "password"}` | `200 {"access_token", "token_type": "bearer"}` · wrong email or password → `401` |

**Login rate limit:** after 5 failed logins for the same email within 60 seconds, further
login attempts for that email return `429` until the minute has passed.

### Projects
| Request | Response |
|---|---|
| `POST /projects {"name"}` | `201 {"id", "name", "owner_id"}` · the creator is the owner |
| `GET /projects` | `200 [project, …]`: projects the user owns or is a member of |
| `POST /projects/{id}/members {"email"}` | `201 {"user_id", "project_id"}` · only the owner may add (member → `403`) · unknown email → `404` |

A user who is neither owner nor member gets `404` for anything under that project
(its issues, members, comments), so the project's existence isn't revealed.

### Issues
Issue: `{"id", "project_id", "title", "description", "status", "priority", "assignee_id", "created_at", "updated_at"}`
- `status`: `open` | `in_progress` | `done` (new issues are `open`)
- `priority`: `low` | `medium` | `high` (default `medium`)

| Request | Response |
|---|---|
| `POST /projects/{id}/issues {"title", "description"?, "priority"?, "assignee_id"?}` | `201 issue` · empty title → `422` · assignee who isn't owner/member → `422` |
| `GET /projects/{id}/issues?status=&priority=&page=1&page_size=20` | `200 {"items": [issue, …], "total", "page", "page_size"}` · newest first · `page_size` max 100 |
| `PATCH /issues/{id}` with any of `title, description, status, priority, assignee_id` | `200 issue` · invalid status or priority → `422` |
| `DELETE /issues/{id}` | `204` · only the project owner (member → `403`) |

### Comments
| Request | Response |
|---|---|
| `POST /issues/{id}/comments {"body"}` | `201 {"id", "issue_id", "author_id", "body", "created_at"}` · empty body → `422` |
| `GET /issues/{id}/comments` | `200 [comment, …]`, oldest first |

## Web UI
- Register and log in.
- Projects page: list projects, create a project.
- Project page: issue list with a status filter, create an issue, change an issue's status, open an issue and add a comment.
- Works on a 390 px wide phone screen and on desktop.

## Stack (fixed)
- **API:** Python 3.12+, FastAPI, uvicorn, SQLAlchemy 2.x, Alembic migrations, PyJWT,
  argon2 or bcrypt for passwords, pydantic-settings. SQLite for local runs and tests;
  PostgreSQL in Docker Compose. `uv` for the project.
- **Web:** React + Vite + TypeScript, ESLint, Vitest + Testing Library.
- **Tooling:** pytest + pytest-cov (+ httpx for the test client), ruff, mypy `--strict`.

## Quality bar
- Every endpoint tested, including the error and permission cases. API coverage ≥ 85%.
- `ruff check` and `mypy --strict` pass. ESLint and the TypeScript build pass. Vitest tests for the main screens pass.
- Layered API: routes → services → repositories; database access only in repositories.
- Passwords hashed, secrets only from environment variables, `.env.example` provided.
- Structured (JSON) logs with a request id on every request.
- `Dockerfile` for the API and `docker-compose.yml` (api + postgres + web) that starts the whole app.
- GitHub Actions workflow running the API and web checks.
- `README.md`: how to run locally and with Docker, how to test, and a short architecture overview.
- Runs locally with `uv` on port 8000 against a fresh SQLite database, with the README's commands.

## Not included
Email verification, password reset, refresh tokens, real-time updates, file uploads,
deployment to a cloud provider.
