---
type: llm
focus: trace
weight: 2
---

The user ran "/setup-project fix …" to report a bug in a project the dev team already built.
There is no setup-project repo (no STATE.md) in the current folder.

PASS if the assistant treated it as a bug report for an existing project: it asked which
project or repository the bug is in, or said it needs the finished project's folder (or
`/setup-project resume <repo>` / the repo name) before it can reproduce and fix the bug.
FAIL if it treated "fix the save button…" as a new idea: started the intake opener for a new
project, asked for a new repository name, or began a spec interview about it.
