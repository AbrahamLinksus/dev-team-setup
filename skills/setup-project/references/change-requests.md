# Change requests

A change request (CR) is anything the owner says that changes **what** is being built or
**how** it's designed, as opposed to fixing one task's result. Examples: "make it work
offline", "add login", "drop the export feature", "use Postgres instead".

## Detecting one

- During a task card, "Request changes" that touches behaviour outside that task's
  acceptance criteria, a story, a flow, a non-goal, the stack or a contract → it's a CR.
- Any free-text message mid-build that changes scope or design → it's a CR.
- Unsure → ask: "Is this a fix to T-07, or a change to the project?" (two options).

## Flow

```
1 Pause      no new tasks start; running steps finish and checkpoint. Approvals are HELD:
             taskgit refuses to approve any task while a CR branch is open (exit 8). Cards
             already waiting stay queued; tell the owner they'll be shown again after the CR.
2 Branch     $TASKGIT start <repo> CR-<n>
3 Update     planner → SPEC.md (+ wireframes if screens change); HLD.md if modules/flows change
             architect → LLD.md / CONVENTIONS.md (+ .devteam/scopes.json) if design changes
             researcher first, if a new library/service is needed
4 Impact     planner writes the impact on tasks to `## Task impact` in its full report (not yet applied):
               Done tasks needing rework · open tasks affected · tasks added / removed / changed
5 Card ⏸     "What changes" card (below). Approve / Request changes / Cancel CR
6 Re-plan    planner revises TASKS.md on the CR branch (rework tasks get new IDs, e.g. T-07b).
             The CR branch owns TASKS.md only; STATE.md and DECISIONS.md stay main's
             (checkpoint reverts any change to them).
7 Merge      Orchestrator: $TASKGIT approve <repo> CR-<n> "docs: CR-<n> <title>"
             exit 4 = TASKS.md changed on main since the CR branched → planner redoes the
             re-plan on top of current main (sync first), then approve again.
             After the merge: log the CR as a Tier 1 decision in DECISIONS.md and update
             STATE.md in the main checkout, then $TASKGIT record.
8 Resume     offer "Continue in a fresh session (Recommended)" / "Continue here" (fresh session:
             update STATE.md "Next step", record, tell the owner to run /setup-project resume <repo>).
             approvals unblock. Queued cards: re-sync each task ($TASKGIT sync) and re-show
             the card if the CR affected it. Open task branches affected by the CR: sync them
             and brief their owner agent with the doc changes. Unaffected ones continue.
```

Cancel CR → `$TASKGIT reject <repo> CR-<n>`; approvals unblock; resume as before.

**On a finished project** (STATE.md `Complete`), a new feature is a CR too, with a fresh size
estimate for the change alone, its own milestone and a short handover: `maintenance.md`.

New packages, a changed stack or a changed contract inside a CR still get their own
Tier 1 decision cards in step 5.

## "What changes" card

```
CR-2 · Work offline

SPEC   + US-09 use the app without internet; changes sync when back online
       ~ F-2 create todo: saved locally first
       − non-goal "offline support" removed
HLD    + Sync module (local store ↔ API)
LLD    + IndexedDB store via idb; + /api/todos/sync endpoint; TodoApi gains sync()
TASKS  rework: T-05 (frontend data layer) → T-05b
       new: T-12 sync endpoint · T-13 offline queue · T-14 sync conflict tests
       removed: none · milestone M2 grows from 4 → 7 tasks
New packages: idb 8.x (Tier 1, separate card)
```

Visual: the updated HLD/LLD diagram, with the changed parts noted in the caption, and
updated wireframes if screens changed.
