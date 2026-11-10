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
  session (covered by Anthropic's own terms and privacy policy), plus the actions listed in the
  README's [What this plugin runs and sends](../README.md#what-this-plugin-runs-and-sends):
  pushes to your repo, package installs from public registries, and web pages fetched by the
  research-type agents when the plan uses them.

Questions: open an issue at https://github.com/AbrahamLinksus/dev-team-setup/issues
