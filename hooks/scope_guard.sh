#!/bin/sh
# PreToolUse entry point for the scope guard.
# Almost every tool call, in every session, comes from something other than this plugin's
# agents. Answer those here, without starting Python; hand the rest to scope_guard.py.
input=$(cat)
case "$input" in
  *'"agent_type"'*) ;;
  *) exit 0 ;;   # main session: no agent_type at all
esac
printf '%s' "$input" | grep -q '"agent_type"[[:space:]]*:[[:space:]]*"dev-team-setup:' || exit 0
printf '%s' "$input" | exec python3 "$(dirname "$0")/scope_guard.py"
