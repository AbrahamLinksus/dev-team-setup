# Result cards

## Per-task card

Order: the image(s) first (SendUserFile), then the card (SendUserMessage), then the
approval question (AskUserQuestion). Keep the card mobile-readable.

```
T-07 · Login API · backend-coder

GOAL (from TASKS.md)            ACHIEVED
• POST /login returns JWT       ✅ done
• 401 on wrong password         ✅ done
• Rate limit 5/min              ⚠️ partial — limit works, no lockout message

Changes: 4 files, +182 / −12
  auth.py, routes.py, test_auth.py, .env.example
Tests: 14/14 passed · coverage 86%
Conventions: lint ✅ · types ✅ · max complexity 7 · layers ✅ · SOLID review: 0 major, 1 minor
Reviewer: 1 minor — hardcoded token expiry (auth.py:41)
Agent decisions: bcrypt for hashing (D-12)
```

Rules:
- Copy the GOAL bullets verbatim from the task's acceptance criteria in TASKS.md.
- Mark each one ✅ done / ⚠️ partial (say what's missing) / ❌ not done (say why).
- Copy the Conventions line from the tester's report and the SOLID counts from the reviewer's.
- Get the change summary from `$TASKGIT diffstat <repo> <id>`, and
  list the 3–5 most important changes in one line each.
- If any goal is ⚠️ or ❌, put a line above the card: "⚠️ Not all goals met."
- Offer the full diff on request (send it as a .diff file).

## Approval question

AskUserQuestion, header `T-07`:
- **Approve** (or **Accept partial** when any goal is ⚠️/❌): commit + push, status Done
- **Request changes**: Jake types what; the same owner agent reworks it
- **Reject**: revert the task's changes; status Backlog with Jake's reason

The approval covers the push; don't ask about the push separately.

## Milestone card

```
Milestone 2 · Auth + core API · 5/5 tasks

TASK                     GOALS   RESULT
T-05 User model          3/3     ✅
T-06 Register API        4/4     ✅
T-07 Login API           2/3     ⚠️ accepted partial
...
Open issues: rate-limit lockout message (carried to M3)
Decisions this milestone: D-09…D-14
Next milestone: M3 · RAG pipeline (6 tasks)
```

Visual: before/after of the whole project (e.g. app screenshot then vs now, or a
metrics chart vs baseline, or an updated architecture diagram).
Ask: Approve milestone / Request changes.
