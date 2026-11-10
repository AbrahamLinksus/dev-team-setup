# Result cards

## Per-task card

Order: the image(s) first, then the card, then the approval question (AskUserQuestion).
Keep the card mobile-readable.

**How to deliver it depends on the surface** (check once per session with ToolSearch, and
record the result in STATE.md so a resume doesn't re-check):
- **SendUserFile + SendUserMessage available** (Claude app, remote/phone sessions): images with
  SendUserFile, the card with SendUserMessage.
- **Not available** (terminal CLI, IDE extensions): write the card to
  `<wt>/.results/<id>/card.md` (images linked by relative path), then print in your reply the
  card text itself plus the **absolute paths** of the images, so the owner can open them
  (most terminals make paths clickable). Never skip the images because they can't be sent:
  the paths are the fallback.
- AskUserQuestion works everywhere; it stays the way the owner answers.
- PushNotification is optional: without it, say nothing about notifications.

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
- Copy the Conventions line from the tester's short REPORT (its Checks line) and the SOLID
  counts from the reviewer's. Build the card from short REPORTs; open a full report only
  for a detail the card needs.
- Get the change summary from `$TASKGIT diffstat <repo> <id>`, and
  list the 3–5 most important changes in one line each.
- If any goal is ⚠️ or ❌, put a line above the card: "⚠️ Not all goals met."
- Offer the full diff on request (send it as a .diff file).

## Approval question

AskUserQuestion, header `T-07`:
- **Approve** (or **Accept partial** when any goal is ⚠️/❌): commit + push, status Done
- **Request changes**: the owner types what; the same owner agent reworks it
- **Reject**: revert the task's changes; status Backlog with the owner's reason

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
LLD as-built: 3 changes (TokenService split from AuthService · /login returns expires_at · users.email unique)
Decisions this milestone: D-09…D-14
Next milestone: M3 · RAG pipeline (6 tasks)
```

Visual: before/after of the whole project (e.g. app screenshot then vs now, or a
metrics chart vs baseline, or an updated architecture diagram).
Ask (AskUserQuestion, header `M<n>`):
- **Approve + continue in a fresh session (Recommended)**: update STATE.md "Next step",
  `$TASKGIT record`, then tell the owner: "Start a new chat and run
  `/setup-project resume <repo>`". A fresh session starts with an empty context, which keeps
  later milestones as cheap as the first.
- **Approve and continue here**
- **Request changes**

Send the LLD "Changes since last milestone" section rendered as an image when there are
changes. Offer the same fresh-session choice after a change request merges.

## Handover card (project end)

Images: running app (or main output) screenshot, the as-built system diagram, README
"How to run" rendered. Then a list of what was delivered: `docs/ARCHITECTURE.md`,
`docs/WALKTHROUGH.md`, README sections, CI status, final coverage, open issues / tech debt.
Ask: Approve handover / Request changes.
