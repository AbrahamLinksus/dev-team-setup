#!/bin/sh
# PreToolUse entry point for the scope guard.
# Almost every tool call, in every session, comes from something other than this plugin's
# agents. Answer those here, without starting Python; hand the rest to scope_guard.py.
#
# For our agents this script fails closed: if Python is missing, crashes or is about to hit
# Claude Code's hook timeout, it denies the call itself. (Claude Code treats a hook that
# can't run as a non-blocking error and would let the call through.)
input=$(cat)
case "$input" in
  *'"agent_type"'*) ;;
  *) exit 0 ;;   # main session: no agent_type at all
esac
printf '%s' "$input" | grep -q '"agent_type"[[:space:]]*:[[:space:]]*"dev-team-setup:' || exit 0

deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[dev-team scope] %s"}}\n' "$1"
  exit 0
}

py=""
for cand in "${DEVTEAM_PYTHON:-}" python3 python; do
  [ -n "$cand" ] || continue
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    py=$cand; break
  fi
done
[ -n "$py" ] || deny "the scope guard needs Python 3.9+ (python3) and none was found, so every call from this plugin's agents is blocked. Install Python 3, then retry."

guard="$(dirname "$0")/scope_guard.py"
if command -v timeout >/dev/null 2>&1; then
  out=$(printf '%s' "$input" | timeout 20 "$py" "$guard"); rc=$?
else
  out=$(printf '%s' "$input" | "$py" "$guard"); rc=$?
fi
[ "$rc" -eq 124 ] && deny "the scope guard timed out; blocked to be safe"
[ "$rc" -ne 0 ] && deny "the scope guard failed (exit $rc); blocked to be safe"
[ -n "$out" ] && printf '%s\n' "$out"
exit 0
