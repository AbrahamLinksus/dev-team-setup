---
type: llm
focus: trace
weight: 2
---

Read every message the assistant shows the user, and every question and option text in its
AskUserQuestion calls, up to the end of the run.

The user said they don't write code, so the plugin must talk to them in builder mode.

PASS if all of these hold:
- no package, framework, library, language or tool name (for example React, FastAPI, SQLite,
  Postgres, pytest, ruff, Docker, uv, npm, Playwright, Mermaid) appears without a plain-words
  explanation next to it, unless it sits on a line marked as technical detail the user can skip;
- no unexplained jargon such as "HLD", "LLD", "worktree", "Tier 1", "scaffold", "CI", "repo"
  without a short gloss the first time it is used;
- questions say what each choice means for the user (for example "nothing leaves this computer")
  rather than only naming a technical option.
PASS also if the run stopped early because a requirement such as Python 3.9+ is missing, as long
as that message itself is in plain words.
FAIL if any user-facing text breaks one of the rules above; quote the offending words.
