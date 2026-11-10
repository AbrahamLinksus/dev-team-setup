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
Affects: <files / tasks / cost>
```

## Decision card (what the Orchestrator sends the owner)

Use AskUserQuestion: the question holds the context in ≤2 lines; 2–4 options, with
the recommended one first and labelled "(Recommended)"; each option's description holds
its trade-off. Add a diagram or table image first if it helps compare the options.

Log every Tier 1 answer in `DECISIONS.md`:

```
| ID | Date | Decision | Chosen | Alternatives | Decided by | Task |
| D-07 | 2026-11-09 | Vector DB | Qdrant | pgvector, Chroma | the owner | T-04 |
```
