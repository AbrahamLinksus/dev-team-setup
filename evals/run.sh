#!/bin/sh
# Run the plugin's eval suite (D33). Each group needs its own tool grants, so it's three runs.
# Costs model calls on your credential; each group is capped. Extra args go to every run,
# e.g.  sh evals/run.sh --runs 1
set -u
cd "$(dirname "$0")/.." || exit 1
CLAUDE=${CLAUDE_BIN:-claude}
common="--trust-plugin --ablation none --threshold 0.8 --no-publish"
rc=0
# routing: does the skill start when it should, and stay out of the way when it shouldn't
$CLAUDE plugin eval . $common --tag routing --max-cost-usd 3 --json evals/results/routing.json "$@" || rc=1
# surface: claude.ai chat has no Agent tool or Bash; the skill must stop, not run unguarded
$CLAUDE plugin eval . $common --tag surface --disallow-tools Agent Bash --max-cost-usd 3 \
  --json evals/results/surface.json "$@" || rc=1
# intake: the opener comes before the first question; plain words in builder mode (Bash lets intake check python3)
$CLAUDE plugin eval . $common --tag intake --allow-tools Bash --max-cost-usd 8 \
  --json evals/results/intake.json "$@" || rc=1
exit $rc
