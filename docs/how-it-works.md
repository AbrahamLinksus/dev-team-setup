# How it works

The detailed version: the pipeline, the agent team, the guardrails and the files each
project gets. For getting started, see the [README](../README.md).

## Flow

```
Idea → repo (you choose: private, public, or try locally) → "Do you write code?"
→ Spec interview: rounds of questions until SPEC.md is complete (data safety always asked)
  → product-critic tests the spec against realistic scenarios; its gaps are asked on the spec card ⏸
  → size from risk signals (small · medium · large) and the design path
→ Design, one of two paths:
    one design step (most projects): LLD with a big-picture section + conventions + team ⏸
    separate system design (large, or 2+ separately running parts, or an external service):
      HLD ⏸ → team picked from its modules ⏸ → LLD + conventions + packages ⏸
→ environment install ⏸
→ task list: feature slices with Owner, Depends on and Files; task graph and parallel rounds ⏸
→ build loop: up to 3 tasks at once, each run by a task-runner:
    owner agent → tests (tester, or the coder on low-risk tasks) + review → debugger if needed
    → sync with main → result card with screenshots and "Try this" ⏸
→ each milestone (if more than one): design doc synced to the code, README, phone preview (opt-in) ⏸
→ handover: CI, ARCHITECTURE.md, WALKTHROUGH.md, OWNER.md, production gate, lint ⏸
Anytime: a change request updates the spec and design, shows a "what changes" card ⏸, re-plans, resumes.
After handover: /setup-project fix <bug> · /setup-project add <feature>
```

Every result comes with a visual (screenshot first, then chart/diagram, then table), the
task's goals vs what was achieved, "Try this" steps, its cost, and Approve / Request changes /
Reject. Approving a task squashes its branch into main as one commit and pushes it.

## Right-sizing

- **Size comes from risk, not a guessed task count.** The planner counts risk signals in the
  spec (a backend reachable over the internet, auth, a separate database server, several users
  with their own data, external services or payments, AI/ML, internet hosting): 0–1 small, 2–3
  medium, 4+ large. Size sets the task cap (8 / 15 / 30), the milestone limit (1 / 2 / 4), how
  deep the design goes, and who tests and reviews low-risk tasks.
- **An HLD only when there's something to agree on first.** Most projects get one design step:
  the architect writes the big picture (modules, the stories each serves, the data flow, the
  milestones) as the first section of the LLD, and you approve one design card. The separate
  HLD stage runs only for large projects, ones with several separately running parts, or ones
  that call external services.
- **Small ideas take the quick track:** a default team, one milestone, low-risk tasks approved
  in batches.

## Parallel work without collisions

- **Tasks are feature slices** (data, logic, screen and tests together), never split by layer.
  One foundation task comes first and builds everything shared.
- **`taskgraph.py`** turns TASKS.md into rounds of tasks that can run together, the longest
  chain and a parallel factor. A plan that's too serial (under 1.5), over its task cap or
  milestone limit, or where a feature task claims shared code goes back to the planner and
  architect before you see it.
- **Files are claims.** While a task runs, no other task's agent may write the files it lists,
  and shared code is frozen after the foundation. The guard enforces this. An agent that needs
  another file asks (`Needs file:`) instead of working around it.
- **Task-runners.** Each ready task is handed to its own background task-runner, which starts
  the task's agents itself and returns one finished card. The main session only schedules,
  shows cards and approves, so a whole project fits in one session. Without nested agents it
  falls back to running the steps itself, with a fresh session per milestone.
- **Early sync.** After each approval, the other open task branches take the new main straight
  away, so conflicts show during the task, not at its card.

## How it stays safe

- **Checkpoints:** every agent step is committed and pushed to the task's own `wip/<id>`
  branch, so work survives a session ending mid-task (`/setup-project resume <repo>`). Resume
  also checks that you're running the same plugin version the project started with.
- **Shared files:** `TASKS.md`, `STATE.md` and `DECISIONS.md` are only edited on main, by the
  Orchestrator, and land in the approved task's own commit. Before a card is shown, the task is
  merged with current main and `scripts/check.sh` is re-run.
- **Enforced roles:** a PreToolUse hook (`hooks/scope_guard.sh` → `scope_guard.py`) blocks each
  agent from writing outside its paths, its own task's worktree (each agent is pinned to the
  first worktree it touches) or its task's file claims; from reading or writing `.env` files;
  from running git or `gh` write commands, installing packages, deleting recursively outside
  the worktree, or leaving unbounded background jobs; and from starting any agent that isn't on
  the team. It also inspects commands nested in `bash -c`, `eval`, `$(…)`, `xargs`,
  `find -exec` and `capture.py --cmd`, and fails closed if Python is missing. After every step,
  a scope check compares the worktree with the commit the step started from, so it also
  catches files written through scripts and edits the agent committed itself (it undoes those
  commits), and reverts anything out of scope. Limits live in
  `skills/setup-project/scopes.json`; projects can add to them in `.devteam/scopes.json`
  (`deny` only ever grows). Every rule is listed in [guardrails](guardrails.md).
- **Conventions:** the architect writes `docs/CONVENTIONS.md` (layering, SOLID, limits);
  `scripts/check.sh` enforces lint, strict types, complexity, layer rules and coverage; the
  reviewer checks SOLID on the task's diff.
- **Watchdog:** a step that runs over 3× its usual time (or 20 minutes) is flagged, and its
  agent row shows `stalled?`.

## Handover

The last milestone leads straight into the handover: CI that runs what the README claims (every
stated OS and the minimum runtime version), `docs/ARCHITECTURE.md` and `docs/WALKTHROUGH.md`
written from the as-built design, README run/test/extend, and `OWNER.md`. Small review findings
are fixed rather than listed. Before the card, `taskgit.sh docrefs` checks that every path and
function the docs name exists, and `taskgit.sh lint` checks executable bits, STATE.md
leftovers, merged branches, OWNER.md and the production gate. Approve appears only when no gate
item is open (each one is built and tested, or waived by you with its consequence).

## Agents (28)

Generated from one spec: edit `tools/gen_agents.py`, then run `python3 tools/gen_agents.py`.
Shared rules: `skills/setup-project/references/team-rules.md`.

| Pack | Agents |
|---|---|
| Core software | planner (Opus), product-critic (Opus, writes only its scenarios), task-runner (runs one task's agent steps), researcher, architect (Opus), env-setup, backend-coder, frontend-coder, tester, reviewer (Opus, read-only), debugger (Opus), docs (Haiku), devops, git-pr (Haiku) |
| AI/ML | trainer, evaluator (Opus, LLM-as-judge), rag-engineer, prompt-engineer, agent-engineer (incl. MCP servers), mlops |
| Data science | data-acquisition (incl. scraping), data-cleaner (asks before dropping data, Pandera), eda (notebooks), statistician (Opus, causal inference), modeler (features + time series), explainer (Opus), visualizer, insights-reporter |

Unmarked agents use Sonnet. An agent moves to a bigger model only when you choose it on the
team or design card.

## Usage

- `/setup-project build a RAG assistant over my lecture notes`
- `/setup-project resume <repo>` continues from the repo's `STATE.md` on any device
- `/setup-project fix <what went wrong>` · `/setup-project add <feature>` on a finished project

## Files created in each project

`STATE.md` (where things stand, for resuming), `TASKS.md`, `DECISIONS.md`,
`docs/SPEC.md` + `docs/wireframes/` + `docs/scenarios.md`, `docs/LLD.md` (with the big picture
first, kept as-built), `docs/HLD.md` (only on the separate system design path),
`docs/CONVENTIONS.md`, `docs/PRODUCTION.md` (the production gate), and at handover
`docs/ARCHITECTURE.md`, `docs/WALKTHROUGH.md` and `OWNER.md`. `.results/` holds images and
reports (git-ignored).

## Token use

1. **Section-based context.** The LLD is written in numbered, self-contained sections
   (`§2.1`…), kept stable at every as-built sync, and capped by project size. Each task has a
   `Context:` line (`SPEC US-03 · LLD §2.1, §4 · files: src/auth/*`) listing exactly what its
   agents need, and agents read only those sections.
2. **Briefs list exactly what to read.** Every brief has a `Read:` field built from a per-role
   default plus the task's `Context:`. A missing piece is reported as a `Context gap` and added
   to the project's STATE.md "Context additions".
3. **Short reports, details in files.** Agents write full reports only when someone will read
   them, and return at most 12 lines. The Orchestrator never reads diffs, logs or test output
   itself; it passes file paths to the next agent.
4. **A small main session.** Task-runners keep each task's agent steps out of the main session;
   reviews of low-risk tasks are batched per milestone; the handover's doc check is a script.
5. **Cost you can see.** Every card shows the task's cost and the total; on a subscription it
   shows what the work would cost at API prices. Milestone cards flag tasks that cost over twice
   the median.

## Setup

When you enable the plugin, it asks for:

| Option | What it does |
|---|---|
| `owner_name` | How the Orchestrator addresses you |
| `github_owner` | GitHub user/org for new project repos (visibility is asked every time; empty = try locally) |
| `approval_mode` | `every-task` (default), `batch-low-risk` (low-risk tasks approved together) or `autopilot` (low-risk tasks with every goal met approved automatically; card afterwards with Undo) |
| `cost_mode` | `quality` (default), `balanced` (Sonnet reviewer/debugger on low-risk tasks and for handover docs, 2 debug rounds; recommended on small and medium projects) or `fast` (Sonnet for every role except planner and architect; Opus reviews high-risk tasks) |
| `budget_usd` | Spend at which it pauses and asks (0 = no cap) |

Other notes:
- Visual capture uses Playwright + Chromium (`skills/setup-project/scripts/capture.py`): page
  screenshots, terminal images, Mermaid diagrams, and short GIFs of a flow (`capture.py flow`).
- GPU training runs on Colab/GCP; the trainer prepares the scripts for it.

## Development

```
python3 -m unittest discover -s tests -v   # structure, agents, scope guard, taskgraph, cost (needs pyyaml; pillow for the GIF test)
bash tests/test_taskgit.sh                  # git scenarios against throwaway repos
python3 tools/gen_agents.py                 # regenerate agents/ after editing the spec (--out DIR, --help)
sh evals/run.sh --runs 1                    # behaviour evals (uses your Claude Code login; costs usage)
```

- `tests/test_taskgit.sh` has one scenario per git bug or feature (parallel approvals, change
  requests, push failures, file claims, catch-up, lint, docrefs…). Add a scenario before fixing
  the next bug. `TASKGIT_UNDER_TEST=<path>` runs the suite against another copy of the script.
- `tests/test_scope_guard.py` feeds the hook real JSON events, including known bypass attempts
  (chained commands, `bash -c`, `eval`, substitutions, newlines, wrappers, interpreter
  one-liners, look-alike scripts), file claims and the task-runner's limits.
  `tests/test_taskgraph.py` covers waves, overlaps, the critical path and size limits;
  `tests/test_capture.py` covers capture.py without a browser; `tests/test_usage.py` covers the
  cost line.
- CI (`.github/workflows/ci.yml`) runs all of it on every push and PR, on Linux and macOS
  (bash 3.2) with Python 3.9 and 3.13, and on Windows through Git Bash.
