# Stage 0 · Intake + repo

Part of the /setup-project Orchestrator (SKILL.md). Read this file when the stage starts; the core rules in SKILL.md (step protocol, context budget, rework) still apply.

## 0 · Intake + repo

1. `/setup-project resume <repo>`, or "continue" when this folder has a setup-project STATE.md
   (or the message names the repo) → read `references/resume.md`.
2. Check `python3 --version` (3.9 or newer). The scope guard that keeps every agent in its lane
   runs on it; without it, the guard blocks every agent call. Missing → tell the owner what to
   install and stop: never build without the guard.
   Then run `python3 $CAPTURE doctor` (the plugin's own tooling for visuals: Playwright + Chromium,
   Pillow, markdown, npm for Mermaid). If it reports anything missing, ask once (AskUserQuestion:
   **Install the visual tools** into the plugin's private venv / **Skip visuals** = text cards),
   then run `python3 $CAPTURE doctor --install`. It never touches the project's environment.
   Record the answer in STATE.md.
3. Before the first question, a three-line opener so the owner knows what they're starting:
   ```
   Here's how this goes: a short interview (about 5–15 minutes of your answers), then a plan you
   approve, then the team builds it task by task and shows you each result to approve.
   Small idea? There's a quick track. Each result shows its cost; you can pause any time.
   ```
   Never state a cost that wasn't measured.
   Then restate the idea in one line. One AskUserQuestion call: repo name (2–3 kebab-case
   suggestions) and where it lives: **Private** / **Public** (a GitHub repo) / **Try locally (no
   GitHub)**. **Always ask; never default it.** Offer *Try locally* first when `gh auth status`
   fails, and say what it means: everything works, nothing leaves this computer, and the repo can
   be put on GitHub later (`git remote set-url origin <url> && git push -u origin --all`).
4. **Try locally** → no GitHub at all: `git init --bare -b main <base>/<repo>.git`, then clone it in
   step 5 as usual. It's a real remote, so checkpoints, `approve` and `record` push to it the same
   way; record `Repo: local (<base>/<repo>.git)` in STATE.md and skip the GitHub-only steps
   (CI in handover becomes a local `scripts/check.sh` hook; say so on the handover card).
   **Private / Public** → create `<github_owner>/<repo>`: `gh repo create` if `gh auth status` works; otherwise
   add_repo (`mcp__claude-code-remote__add_repo`, access `push`), and if the repo doesn't
   exist ask the owner to create an **empty** repo with that name and visibility, then retry.
5. Clone into the session's working folder: `<base>/<repo>`, where `<base>` is the folder this
   session runs in (`pwd`). Task worktrees then live next to it in `<base>/<repo>-wt/`, so every
   file the team writes is inside a folder Claude Code already trusts. Anywhere else (e.g.
   `~/projects`) each edit asks for permission, and remote or phone sessions refuse outright.
   If `<base>` is itself a git checkout (the session was started inside another project), ask
   the owner for a folder, then add it with `/add-dir <folder>` before cloning there.
   Record `<base>` in STATE.md. Copy templates: `STATE.md`, `TASKS.md`, `DECISIONS.md` at the
   root; `SPEC.md`, `HLD.md`, `LLD.md`, `CONVENTIONS.md` into `docs/`. `.gitignore`: `.env`,
   `.results/`, `.venv/`, `node_modules/` (env-setup adds the data and model ignores for data/ML work). Commit + push (covered by the visibility answer).
6. `$TASKGIT start <repo> plan`: stages 1–6 run on `wip/plan`.
