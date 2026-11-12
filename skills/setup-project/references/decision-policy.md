# Decision policy

## Tier 1: the owner decides (stop work, ask)

- Architecture, module boundaries, data flow
- Stack, frameworks, languages, databases, vector DBs, hosting
- Adding, removing or upgrading any package
- Model choice (ML algorithm, LLM, embedding model), training budget
- Dropping or modifying data rows/columns, changing the target or metric
- Where datasets and model files live: DVC with a remote, Git LFS, or not versioned at all
  (git-ignored, re-created by a script). Ask before the first data or model file is written;
  never commit them to git by default
- Anything that costs money, uses an external account, or sends data outside
- Deployment target and timing, repo visibility, and any push other than the pre-approved ones:
  `wip/*` checkpoint pushes, and the push that approving a result card (or `record`) already covers
- Anything irreversible or hard to undo
- Changing an approved HLD, LLD, acceptance criterion or milestone
- **Anything you're unsure about**

## Tier 2: the agent decides and logs it

- File, function and variable names inside the agreed structure
- Internal refactors that keep the agreed interfaces
- Test layout, fixtures, helper utilities
- Formatting, docstrings, log messages
- Hyperparameter search ranges inside an approved budget

Each Tier 2 decision is one line in the agent's report → the Orchestrator appends it to
`DECISIONS.md` and lists it on the result card, where the owner can overrule it.

## How agents escalate

A subagent cannot ask the owner directly. When it hits a Tier 1 decision it stops and returns:

```
DECISION NEEDED
Context: <1–2 lines>
Options:
  A) <option> — <trade-off>
  B) <option> — <trade-off>
Recommended: <A/B> because <reason>
For the owner: <what the recommended option means for them, in plain words>
If wrong: <what it costs to change later: an hour, a rework of T-xx, data lost…>
Affects: <files / tasks / cost>
```

## Decision card (what the Orchestrator sends the owner)

Use AskUserQuestion: the question holds the context in ≤2 lines; 2–4 options, with
the recommended one first and labelled "(Recommended)"; each option's description holds
its trade-off. Add a diagram or table image first if it helps compare the options.

Before the question, two lines every decision card has, from the agent's `For the owner` and
`If wrong` (or the architect's list):
- **What this means for you:** the recommended option's effect on the owner's app, in plain words
  ("your recipes stay on this computer; nothing to sign up for").
- **If this is wrong:** what changing it later costs ("about an hour now, a day after T-06").
Technical detail (names, versions, benchmarks) goes in one collapsed `Technical detail:` line
below them, in builder mode only on request.

Then one line: **Why we're asking:** naming the Tier 1 rule above that applies,
in plain words, e.g. "Why we're asking: adding a package is your call (it changes what the
project depends on)." The owner should never wonder why the build stopped.

Log every Tier 1 answer in `DECISIONS.md`:

```
| ID | Date | Decision | Chosen | Means for you · if wrong | Alternatives | Task |
| D-07 | 2026-11-09 | Vector DB | Qdrant | search by meaning works offline · swap ≈ 1 day | pgvector, Chroma | T-04 |
```
