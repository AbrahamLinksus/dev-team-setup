# Spec interview

Goal: turn a one-line idea into `docs/SPEC.md` complete enough that the HLD needs no
guesses. Interview in rounds until the checklist is complete, for **at most 6 rounds**: every
round an Opus planner re-reads the growing SPEC, so an open-ended interview gets expensive and
tiring. After round 6 the planner writes each still-open item into SPEC.md as an explicit
assumption (marked "(assumed)") and returns SPEC COMPLETE; the spec card lists those assumptions
so the owner can correct any of them before the HLD.

## Loop

```
round n:
  planner reads SPEC.md + all answers so far
    → updates SPEC.md
    → returns a QUESTIONS block for the gaps (max 4, most important first)
  Orchestrator asks them (one AskUserQuestion call; options from the block, recommended first,
    always include "Decide for me" when a sensible default exists)
  answers go back to the planner in the next brief (verbatim)
until planner returns "SPEC COMPLETE", or round 6 is answered: then the brief says
  "final round: turn every open item into an (assumed) line and return SPEC COMPLETE"
then: product-critic (scenarios + gaps) → wireframes (UI projects) → spec card ⏸
```

## Spec critic (after SPEC COMPLETE, before the spec card)

Spawn **product-critic** (`Read: docs/SPEC.md`). It writes 8–15 realistic usage scenarios with
edge data to `docs/scenarios.md` and checks the spec handles each, returning
`GAPS: <n> (high <h>, medium <m>, low <l>)`. On the spec card:
- **High gaps** become questions in the same AskUserQuestion call as the approval (max 3, from
  the critic's `## Gaps` lines, options included); answers go to the planner for one more round
  (it doesn't count toward the 6), then the card is sent again.
- Medium and low gaps are listed on the card in one line each; the owner can promote any.
- No gaps → one line: "Checked against <s> real-life scenarios: no gaps found."

Between rounds, send the owner a one-line progress note:
"Spec round 2 done: 7/13 sections complete; next: data + non-functional".

## Completeness checklist (planner checks every round)

One row per section of `templates/SPEC.md` (13), so progress is always "x/13 complete".

| Section | Complete when |
|---|---|
| Goal | What it does and why, in one paragraph |
| Users | Who uses it, and in what situation |
| User stories | Every feature the owner mentioned is a story with a checkable acceptance line |
| Main flows | Each story belongs to a step-by-step flow, including what happens on errors |
| Inputs/outputs | At least one concrete example per flow (real-looking values, not placeholders) |
| Data | What's stored, its source, and its rough volume |
| Screens | (UI) every screen named with its key elements; (no UI) "none: CLI/API/library" |
| Integrations | Every external service named, or "none" |
| Non-functional | Scale, latency, offline, security/privacy, cost, platforms each answered or "not a concern" |
| Constraints | Stack preferences/bans, deadline, deployment target answered or "none" |
| Non-goals | At least 3 explicit non-goals (the likeliest scope creep) |
| Done | 3–6 observable outcomes the owner can check themselves |
| Data safety | Backup, second device, what a wipe loses, and undo each answered **by the owner**, never *(assumed)* |

"Decide for me" answers are filled in by the planner and marked *(assumed)*; they are
listed together on the spec card so the owner sees every assumption once.
**Data safety is the exception:** its questions never offer "Decide for me", and in the final
round an open data-safety item becomes a question on the spec card instead of an assumption.
Whatever the owner chose, the card states its consequence in one line ("No backup: if this phone
is lost or reset, every recipe is gone").

## QUESTIONS block (planner output)

```
QUESTIONS (round 2 · 7/13 complete)
1. [Data] Should todos sync across devices? | options: No, this device only; Yes, needs accounts; Decide for me | recommended: No, this device only | why: decides storage + auth
2. ...
```
or
```
SPEC COMPLETE
Assumptions: <list of (assumed) lines>
Screens: <list> (or "no UI")
Size: <small|medium|large> · signals: <the risk signals present, or none> · <n> stories
```

Rules for good questions: one decision per question; options must be concrete and
mutually exclusive; ask about behaviour and outcomes, never about implementation
(that's the HLD/LLD's job); ask the question whose answer removes the most guessing first.

## Wireframes (projects with a UI)

After SPEC COMPLETE, the planner writes one lo-fi HTML file per screen to
`docs/wireframes/<screen>.html`: grayscale boxes, real labels and example data from §5,
no colours, logos or styling libraries, a 390px-wide mobile layout plus a desktop one if
the spec says desktop. The Orchestrator renders each one:

```
python3 $CAPTURE html docs/wireframes/<screen>.html docs/wireframes/<screen>.png --width 390
python3 $CAPTURE html docs/wireframes/<screen>.html docs/wireframes/<screen>-desktop.png --width 1280
```

The PNGs are committed with the spec (they're part of the handover).

## Spec card ⏸

The critic's gaps come first (see Spec critic above). Images: wireframes (max 4; offer the rest on request) + the spec rendered with
`$CAPTURE md docs/SPEC.md` if it fits on 2 screens, otherwise a summary table:
stories · flows · screens · non-goals · done criteria · assumptions.
Ask: Approve spec / Request changes (type them) / Answer more questions.
