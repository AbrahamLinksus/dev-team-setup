# Team rules (every /setup-project agent)

The single source of these rules. Every agent reads this file before starting.
"The owner" is the person running /setup-project; only the Orchestrator talks to them.

## Before you start
- Work only inside the worktree path in your brief (the task's own `wip/<id>` branch). Never touch the main checkout.
- Read your task in the brief, then `docs/HLD.md`, `docs/LLD.md`, `docs/CONVENTIONS.md` (whichever exist), and `TASK_PROGRESS.md` if present (earlier steps of this task).
- `TASKS.md`, `STATE.md`, `DECISIONS.md` and `TASK_PROGRESS.md` belong to the Orchestrator. Read them; never edit them (the planner may write `TASKS.md` during planning only).

## Scope is enforced
- Each role may only change certain paths and run certain shell commands (`skills/setup-project/scopes.json`, plus the project's `.devteam/scopes.json`). A hook blocks out-of-scope writes and commands, and after every step the Orchestrator reverts any out-of-scope file changes. If a block stops you from finishing, report it under Issues; don't try to work around it.
- No git write commands (the Orchestrator and git-pr own history). No package installs except env-setup with an approved plan.

## Decisions
- **Tier 1 = the owner decides.** Stack, frameworks, adding/removing/upgrading packages, architecture or interface changes, model choice, dropping or changing data, anything that costs money, uses an external account, is irreversible, or that you're unsure about → stop and return `DECISION NEEDED` (format below).
- **Tier 2 = you decide and log it.** Names, internal refactors that keep the agreed interfaces, test layout, formatting. List each under "Agent decisions".

## Quality
- Follow `docs/CONVENTIONS.md` (layering, SOLID rules, limits). Code you write must keep `scripts/check.sh` passing.
- Never write secrets into tracked files; use `.env` (git-ignored) and document keys in `.env.example`.
- Produce visual evidence with the capture script (path in your brief as `CAPTURE`) into `.results/<task-id>/`. Prefer screenshots; then chart → diagram → rendered table.
- Never leave servers or background processes running when you finish.

## Output: return exactly one of these

```
REPORT <task-id> · <your name>
Goals:
  - <acceptance criterion, verbatim> — ✅ done | ⚠️ partial: <what's missing> | ❌ not done: <why>
Changes: <files created/modified, one per line>
Visuals: <image paths in .results/<task-id>/>
Checks run: <command> → <result>
Agent decisions:
  - <Tier 2 decision> — <reason>
Issues / follow-ups:
  - <anything the Orchestrator or the owner should know>
```

```
DECISION NEEDED
Context: <1–2 lines>
Options:
  A) <option> — <trade-off>
  B) <option> — <trade-off>
Recommended: <A/B> because <reason>
Affects: <files / tasks / cost>
```
