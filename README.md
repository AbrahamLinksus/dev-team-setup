# dev-team-setup

Turn an idea into a working project with a team of AI agents.
You answer questions and approve each step, from your laptop or your phone.

![From idea to handover](docs/images/how-it-works.png)

---

## Get started

**1. Install** in Claude Code

```bash
claude plugin marketplace add AbrahamLinksus/dev-team-setup
claude plugin install dev-team-setup@dev-team-setup
```

**2. Add your details:** your name and GitHub username

```
/plugin configure dev-team-setup@dev-team-setup
```

**3. Start a project**

```
/setup-project a habit tracker with daily streaks
```

That's it. Claude asks you a few questions, plans the project, picks a team of agents,
and starts building.

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

Change these with `/plugin configure dev-team-setup@dev-team-setup`.

| Setting | Default | What it does |
|---|---|---|
| `approval_mode` | `every-task` | Set `batch-low-risk` to approve small, safe tasks together |
| `cost_mode` | `quality` | Set `balanced` to use cheaper models where it's safe |

---

## Learn more

- [How it works](docs/how-it-works.md): the agents, the guardrails, the files each project gets
- [Example run](examples/todo-app/): real planning output for a small todo app

**Contributing:** run the tests before you push.

```bash
python3 -m unittest discover -s tests   # needs pyyaml
bash tests/test_taskgit.sh
```
