---
type: llm
focus: trace
weight: 2
---

Look at the assistant's text up to and including the first AskUserQuestion tool call that asks
for a repository name or where the project should live.

PASS if, before that question, the assistant told the user in a few lines what is about to
happen: an interview or questions about the idea, then a plan for them to approve, then the app
built step by step with results shown for approval.
PASS also if the run ended before any repository question because it first asked about
installing visual tools, or stopped because a requirement (such as Python 3.9+) is missing and it
said which.
FAIL if it asked for the repository name or visibility without that explanation, or if it
started writing project files before asking anything.
