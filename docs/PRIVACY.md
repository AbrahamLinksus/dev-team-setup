# Privacy

dev-team-setup is a Claude Code plugin: instructions, agent definitions and local scripts. It
has no server of its own and collects nothing.

- **No telemetry.** The plugin sends no usage data, analytics or crash reports anywhere.
- **Your project stays where you put it:** on your computer, and in the GitHub repo it creates
  for you, under your account, private or public as you choose (or only on your computer with
  **Try locally**).
- **Local records** (`.git/devteam-*` files: timing, guard blocks, agent pins, check results)
  stay inside your project's `.git` folder and are never pushed.
- **What leaves your computer** is what Claude Code itself sends to Anthropic's API during your
  session (covered by Anthropic's own terms and privacy policy), plus the actions listed in
  [What this plugin runs and sends](#what-this-plugin-runs-and-sends) below:
  pushes to your repo, package installs from public registries, web pages fetched by the
  research-type agents when the plan uses them, and, only if you opt in at a milestone, a
  temporary public preview link to the running app through a tunnel service (it closes after
  30 minutes).
- **Cost figures** on result cards are read from Claude Code's own session logs on your computer;
  nothing is sent anywhere to compute them.

## What this plugin runs and sends

Everything runs on your machine, in your Claude Code session. The plugin has no server and
no telemetry. It sends nothing anywhere except what is listed here.

| What | When | Where it goes |
|---|---|---|
| Creates a GitHub repo (`gh repo create`), private or public as you choose | Once, at the start of a project (not with **Try locally**) | GitHub, under the account you set as `github_owner` |
| Pushes commits: `main` and one `wip/<task>` branch per task, after every step | Throughout the build, so work survives a closed session | That repo |
| Installs the project's own dependencies (`uv sync`, `npm ci`, …) | When a task starts in its own worktree | Package registries (PyPI, npm); files stay in the project folder |
| Installs Playwright, Chromium, Pillow and `mermaid@11.4.1` for screenshots and diagrams | Only when you say yes to `capture.py doctor --install` | Into the plugin's private data folder, not your system Python |
| Shows each working agent's task, step, time and tokens in Claude Code's agent panel (`settings.json` → `hooks/subagent_status.sh`) | While agents run | Nowhere: it formats what Claude Code passes it |
| Starts a headless browser on `localhost` | To screenshot each result | Nowhere: local pages only |
| Fetches web pages and searches the web | Only the researcher, rag-engineer, agent-engineer and data-acquisition agents, and only when the plan picks them | The sites they read |
| Opens a temporary public link to the running app (`cloudflared` or `npx localtunnel`) | Only if you say yes at a milestone; closes after 30 minutes | The tunnel service; anyone with the link can use that build while it's open |
| Reads Google Drive files | Only the data-acquisition agent, only if you connected Google Drive and point it at a file | Read-only |

**The guard.** A hook (`hooks/scope_guard.sh`, which runs `hooks/scope_guard.py`) checks every
file edit and shell command made by the plugin's own agents, and blocks anything outside that
agent's role: for example, the tester can't edit app code, and no agent can read `.env` files,
push to `main`, or delete outside the project. It runs locally, makes no network calls, and
ignores tools used outside the plugin's agents. Each block is noted in `.git/devteam-guard.log` (local, never
pushed) so the result card can tell you about it. When it can't run (no Python 3.9+), it blocks
the agent's action rather than letting it through. The full rules are in
[how it works](how-it-works.md).

Questions: open an issue at https://github.com/AbrahamLinksus/dev-team-setup/issues
