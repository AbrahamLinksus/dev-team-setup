# Team rules (every /setup-project agent)

The single source of these rules. Every agent reads this file before starting.
"The owner" is the person running /setup-project; only the Orchestrator talks to them.

## Before you start
- Work only inside the worktree path in your brief (the task's own `wip/<id>` branch). Never touch the main checkout.
- Your shell and tools do **not** start in the worktree. Use the absolute paths from your brief with Read, Write and Edit, and start every Bash command with `cd <worktree> &&` (e.g. `cd /home/me/projects/todo-wt/T-03 && uv run pytest -q`). Relative paths would read or change the main checkout.
- Read only what your brief's `Read:` field lists. If you need something that isn't listed, read just that section and add `Context gap: <what and why>` under Issues.
- When `Read:` names document sections (`docs/LLD.md §2.1, §4`), read only those sections, not the whole file: Grep the file for the section headings (`^#+ §2\.1`, `^#+ §4`) to get their line numbers, then Read with `offset` and `limit` up to the next heading at the same level. Every agent start pays for what it reads.
- `TASKS.md`, `STATE.md`, `DECISIONS.md` and `TASK_PROGRESS.md` belong to the Orchestrator: never edit them (only the planner writes `TASKS.md`, during planning and change requests). Read them only when your `Read:` field lists them.

## Scope is enforced
- Each role may only change certain paths and run certain shell commands (`skills/setup-project/scopes.json`, plus the project's `.devteam/scopes.json`). A hook blocks out-of-scope writes and commands, and after every step the Orchestrator reverts any out-of-scope file changes. If a block stops you from finishing, report it under Issues; don't try to work around it.
- No git write commands (the Orchestrator and git-pr own history). No package installs except env-setup with an approved plan.

## Decisions
- **Tier 1 = the owner decides.** Stack, frameworks, adding/removing/upgrading packages, architecture or interface changes, model choice, dropping or changing data, anything that costs money, uses an external account, is irreversible, or that you're unsure about → stop and return `DECISION NEEDED` (format below).
- **Tier 2 = you decide and log it.** Names, internal refactors that keep the agreed interfaces, test layout, formatting. List each under "Agent decisions".

## Quality
- Follow `docs/CONVENTIONS.md` (layering, SOLID rules, limits). Code you write must keep `CHECK_NO_COVERAGE=1 scripts/check.sh` passing: lint, types, complexity, layers and the existing tests. The coverage threshold belongs to the Tester, the only role that runs plain `scripts/check.sh` and writes tests.
- Never write secrets into tracked files; use `.env` (git-ignored) and document keys in `.env.example`.
- Produce visual evidence with the capture script (path in your brief as `CAPTURE`) into `.results/<task-id>/`. Prefer screenshots; then chart → diagram → rendered table.
- Never leave servers or background processes running when you finish. Start anything that runs in the
  background with `timeout <seconds>` (e.g. `timeout 120 uvicorn app:app & …`) and stop it when done; the scope
  guard blocks unbounded `&`, `nohup`, `setsid` and `disown`.

## Output

1. Write a **full report** to the path in your brief (`Write full report to:`) **only when
   someone will read it**, which is when at least one of these holds:
   - a check or test failed, or a goal is ⚠️ or ❌ (the debugger reads the failure output);
   - you found Critical or Major issues (reviewer findings, the debugger's root cause);
   - your duties name a full-report section (e.g. `## Task impact`, `## Needs the owner's approval`);
   - the short REPORT would exceed 12 lines;
   - the brief says `Write full report to: <path> · always`.
   Otherwise write no full report and put `Full report: none` in your REPORT: output costs
   five times as much as input, and an unread report is pure cost. When you do write one,
   it holds every changed file with a one-line summary, the full output of the checks you
   ran, your reasoning, all findings, every Tier 2 decision with its reason, and the
   sections your role's duties ask for.
2. Return a **short REPORT of at most 12 lines**, always. Details belong in the full report, not here:

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
Full report: <path> | none
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

**Planner, during the spec interview only**, returns one of its interview formats instead of a
REPORT (layout in `spec-interview.md`):

```
QUESTIONS (round <n> · <x>/<total> complete)
1. [Area] <question> | options: <a>; <b>; Decide for me | recommended: <a> | why: <what it decides>
...
```
or, when every checklist row is answered:
```
SPEC COMPLETE
Assumptions: <list of (assumed) lines>
Screens: <list> (or "no UI")
Size: <small|medium|large> · ≈<n> tasks · <one-line reason>
```
Every other step, the planner returns a REPORT or DECISION NEEDED like everyone else. These
three are the only formats the Orchestrator accepts.
