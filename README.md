# dev-team-setup

Turn an idea into a working project with a team of AI agents.
You answer questions and approve each step, from your laptop or your phone.

![From idea to handover](docs/images/how-it-works.png)

---

## Get started

**0. Check the requirements**

| You need | Why |
|---|---|
| [Claude Code](https://claude.com/claude-code) 2.1.271 or later | runs the plugin (older versions can't load its settings' choice lists) |
| `git` | every task is a branch with checkpoints |
| [GitHub CLI](https://cli.github.com) `gh`, signed in (`gh auth login`) | creates the project's repo and pushes to it |
| Python 3.9 or newer (`python3`) | the guard that keeps each agent in its lane runs on it |
| [uv](https://docs.astral.sh/uv/) | Python projects |
| Node.js + npm | JavaScript projects and Mermaid diagrams |

One line to check them all:

```bash
git --version && gh auth status && python3 --version && uv --version && npm --version
```

Playwright and Chromium (for screenshots) are set up the first time you start a project: the
plugin asks first, and installs them into its own private folder, not your system Python.

**1. Install** in Claude Code

```bash
claude plugin marketplace add AbrahamLinksus/dev-team-setup
claude plugin install dev-team-setup@dev-team-setup
```

**2. Add your details:** Claude Code asks for your name and GitHub username when the plugin is
enabled. To change them later, open `/config`: each option has its own row there.

**3. Start a project**

```
/setup-project a habit tracker with daily streaks
```

Claude checks the tools above, asks you a few questions, plans the project, picks a team of
agents, and starts building.

---

## What you'll do

Mostly tap buttons. After every task you get a result like this:

<img src="docs/images/result-card.png" width="320" alt="A task result with goals, test results and Approve / Change / Reject buttons">

*Illustration: each result shows what the task was meant to do, what got done, and a screenshot.*

**Approve** saves it to your repo · **Change** sends it back with your note · **Reject** throws it away.

---

## Good to know

- **Take a break anytime.** Continue later, on any device:
  ```
  /setup-project resume <repo-name>
  ```
- **Changed your mind?** Just say it, e.g. *"make it work offline"*. The plan updates and you approve the change.
- **Your code, your repo.** Each project gets its own GitHub repo. You choose private or public.
- **You own the result.** It ends with docs that walk you through the code.

---

## Settings

Pick these when Claude Code asks after you enable the plugin, or change them later in `/config`.

| Setting | Default | What it does |
|---|---|---|
| `approval_mode` | `every-task` | Set `batch-low-risk` to approve small, safe tasks together |
| `cost_mode` | `quality` | Set `balanced` to use cheaper models where it's safe |

---

## Learn more

- [How it works](docs/how-it-works.md): the agents, the guardrails, the files each project gets
- [Example run](examples/todo-app/): real planning output for a small todo app
- **Benchmark:** `python3 bench.py all` compares a normal Claude Code session with the plugin
  (tokens, cost, your effort, and whether the app works). One file, no setup.

**Contributing:** run the tests before you push.

```bash
python3 -m unittest discover -s tests   # needs pyyaml
bash tests/test_taskgit.sh
```
