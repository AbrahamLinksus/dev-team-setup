#!/bin/sh
# subagentStatusLine entry point (D22): find Python 3.9+ and run subagent_status.py.
# Without Python it prints nothing, so every row keeps Claude Code's default rendering.
for cand in "${DEVTEAM_PYTHON:-}" python3 python; do
  [ -n "$cand" ] || continue
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    exec "$cand" "$(dirname "$0")/subagent_status.py"
  fi
done
exit 0
