# Team rules (every /setup-project agent)

The single source of these rules. Every agent reads this file before starting.
"The owner" is the person running /setup-project; only the Orchestrator talks to them.

## Before you start
- Work only inside the worktree path in your brief (the task's own `wip/<id>` branch). Never touch the main checkout.
- Your shell and tools do **not** start in the worktree. Use the absolute paths from your brief with Read, Write and Edit, and start every Bash command with `cd <worktree> &&` (e.g. `cd /home/me/projects/todo-wt/T-03 && uv run pytest -q`). Relative paths would read or change the main checkout.
- Read only what your brief's `Read:` field lists. If you need something that isn't listed, read just that section and add `Context gap: <what and why>` under Issues.
- `TASKS.md`, `STATE.md`, `DECISIONS.md` and `TASK_PROGRESS.md` belong to the Orchestrator: never edit them (only the planner writes `TASKS.md`, during planning and change requests). Read them only when your `Read:` field lists them.

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

## Output

1. Write your **full report** to the path in your brief (`Write full report to:`): every
   changed file with a one-line summary, the full output of the checks you ran, your
   reasoning, all findings, every Tier 2 decision with its reason, and any sections your
   role's duties ask for (e.g. `## Task impact`, `## Needs the owner's approval`).
2. Return a **short REPORT of at most 12 lines**. Details belong in the full report, not here:

```
REPORT <task-id> · <your name> · <step>
Goals:
  - <acceptance criterion, shortened> — ✅ | ⚠️ <what's missing> | ❌ <why>     (one line each)
Changed files: <n>
Checks: <pass|fail> — <the one-line summary your role defines, or the failing check>
Agent decisions:
  - <Tier 2 decision> — <reason>     (one line each)
Issues: <none | one line each; include any Context gap: …>
Visuals: <image paths in .results/<task-id>/>
Full report: <path>
```
If it would exceed 12 lines, keep one line per goal and summarise the rest as
"Agent decisions: <n>, see full report" / "Issues: <n>, see full report".

Or, when you hit a Tier 1 decision, return this instead (unchanged):

```
DECISION NEEDED
Context: <1–2 lines>
Options:
  A) <option> — <trade-off>
  B) <option> — <trade-off>
Recommended: <A/B> because <reason>
Affects: <files / tasks / cost>
```
