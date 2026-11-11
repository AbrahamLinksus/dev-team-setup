# Unattended mode (answers file)

Used to repeat a run without a person answering cards (for benchmarking). It is on
only when the launch or resume prompt contains `Answers file: <absolute path>` (at its end). Record
that path in STATE.md "Config" so a resumed session keeps the mode.

## Rules

- **Never call AskUserQuestion.** For every question you would ask the owner (spec questions,
  approval cards, decision cards, `DECISION NEEDED` from an agent, change-request or fix
  choices), pick the answer from the answers file's table. When the file doesn't cover a
  case, pick the option marked (Recommended), or else the first option.
- **Log every answer** by appending one line to `answers.log` in the answers file's folder:
  `<ISO time> · <card header> · <question, ≤80 chars> → <answer>`. A benchmark counts these
  lines as the owner's interventions.
- Still produce every card and visual exactly as in an attended run (write it to
  `.results/<id>/card.md` as the CLI fallback says), so cost and time are comparable.
- **Fresh session at a milestone or long-session check:** after it is approved and checkpointed, append
  `MILESTONE DONE <n>` (milestone) or `SESSION DONE` (long-session check, `stage-7-build.md`)
  to `answers.log` and end your turn. The benchmark starts the next
  session with the resume prompt.
- **Handover approved:** append `HANDOVER DONE` to `answers.log` and end your turn.
- **Stopped for good** (the guard or a tool keeps failing, or a Tier 1 decision the answers
  file can't settle): append `STOPPED <one-line reason>` and end your turn.
- Ending a turn for any other reason is a failure of this mode: keep working until one of the
  three lines above applies.
