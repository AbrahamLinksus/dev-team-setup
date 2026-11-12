# Result cards

## Every card, every time

- **One progress line on top:** `Stage 7 Build · Milestone 2/3 · Task 4/12` (planning cards:
  `Stage 4 LLD · planning 4/6`). The owner always knows where the project is.
- **Fixed order:** what happened → what it means for you → what you decide. Images go with
  "what happened"; the question is always last.
- **Owner mode** (STATE.md): in *builder* mode, no package, tool or file name without a plain
  gloss; put technical detail on one last line, `Technical detail: …`, which the owner can skip.
  In *developer* mode, technical terms are fine and the glossary below is skipped.
- **Plain words.** The first time a card in this project uses one of these terms, add its gloss
  once, in brackets, and never again:

  | Term | Gloss |
  |---|---|
  | spec | what the app must do, in your words |
  | HLD | the big-picture plan: the parts of the app and how they talk |
  | LLD | the detailed plan: files, data, interfaces, packages |
  | milestone | a group of tasks that ends in something you can try |
  | worktree | a separate copy of the code where one task is built without touching the rest |
  | check.sh | the project's automatic quality checks (tests, lint, types) |
  | Tier 1 | a decision only you make |

## Planning card (stage 6)

Images: the task graph (`tasks.png`: rounds left to right, critical path highlighted), then the
`taskgraph.py --summary` lines as text: one line per round, the longest chain, the parallel
factor and any warning. The owner sees what runs together before anything is built.

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
Cost: ≈$0.42 this task · $3.10 so far · budget $25 (12%)
Guard: stopped tester once (tried to edit app code) · reverted 0 files
Plan vs actual: 1 file outside the plan (src/shared/tokens.py), added to T-07's Files
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
- The Guard line shows the safety working. Count this task's lines in `<repo>/.git/devteam-guard.log`
  (tab-separated: time, task id, agent, tool, target, reason; `grep -c $'	T-07	'`) plus the files
  `$TASKGIT scope` reverted, and say in plain words what was stopped ("tried to edit app code",
  "tried to read .env"). Nothing blocked or reverted → `Guard: nothing blocked`.
- The Plan vs actual line appears only when `taskgraph.py --undeclared` found files; a file in
  another task's `Files:` is worth a word ("T-09 also plans to change it; it waits for this one").
- The Cost line is `python3 $COST` output, verbatim (task share is an estimate, hence ≈). If it
  can't read the logs, leave the line out rather than guess.

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
Then the **production gate table** (≤5 columns: ID · item in plain words · status · proof):

```
Production gate · 11 items · 9 built + tested · 1 waived · 1 open
G-02 Data survives a restart        ✅ test_restart_keeps_recipes
G-03 Backup / export                ✅ test_export_all_recipes
G-W2 Others can't see your data     ⛔ open: no test acts as another user
G-L1 Works offline                  🟡 waived (D-14): needs a connection to sync
```
Ask: Approve handover / Request changes, and Approve only when no item is open (see
`stage-8-handover.md`).
