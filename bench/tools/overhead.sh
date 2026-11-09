#!/usr/bin/env bash
# Fixed overhead: the same tiny prompt with the plugin disabled and enabled, 3 times each.
# The difference in input tokens is what the plugin adds to every session (skill + agent
# descriptions). Restores the plugin to enabled when done.
#
# Run: bash bench/tools/overhead.sh          (plugin installed as dev-team-setup@dev-team-setup)
set -uo pipefail
PLUGIN=${PLUGIN:-dev-team-setup@dev-team-setup}
RUNS=${RUNS:-3}
TMP=$(mktemp -d); cd "$TMP" || exit 1          # empty folder: no project CLAUDE.md
trap 'claude plugin enable "$PLUGIN" >/dev/null 2>&1; rm -rf "$TMP"' EXIT

measure() {  # prints: input_context output_tokens
  claude -p "Reply with just: ok" --output-format json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
if d.get("is_error"):
    sys.exit("error: " + str(d.get("result")))
u = d.get("usage") or {}
ctx = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
print(ctx, int(u.get("output_tokens") or 0))'
}

declare -A SUM
for mode in without with; do
  if [[ $mode == without ]]; then claude plugin disable "$PLUGIN" >/dev/null 2>&1 || { echo "Is $PLUGIN installed?"; exit 1; }
  else claude plugin enable "$PLUGIN" >/dev/null 2>&1; fi
  SUM[$mode]=0
  for i in $(seq 1 "$RUNS"); do
    read -r ctx out < <(measure) || exit 1
    echo "$mode plugin · run $i · input context: $ctx tokens · output: $out"
    SUM[$mode]=$(( ${SUM[$mode]} + ctx ))
  done
done
w=$(( ${SUM[without]} / RUNS )); p=$(( ${SUM[with]} / RUNS ))
echo
echo "Average input context without plugin: $w"
echo "Average input context with plugin:    $p"
echo "Plugin overhead per session start:    $(( p - w )) tokens"
