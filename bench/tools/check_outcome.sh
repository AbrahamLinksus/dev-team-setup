#!/usr/bin/env bash
# Quality numbers for a finished run: API tests/coverage/lint/types, web build/lint/tests,
# and the production files (Docker, CI, migrations, .env.example, README).
#
# Run:  bash ~/dev-team-setup/bench/tools/check_outcome.sh <project folder> [--docker]
#       --docker also validates and builds docker compose (slow; needs Docker running)
set -uo pipefail
P=${1:?usage: check_outcome.sh <project folder> [--docker]}; P=$(cd "$P" && pwd)
DOCKER=${2:-}
ok()  { [[ $1 == 0 ]] && echo "✅" || echo "❌"; }
find_one() { find "$P" -name "$1" -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/.git/*' | head -1; }

# ---- API (Python) ----------------------------------------------------------------------
API_ROW="| n/a | | | | | |"
PY=$(find_one pyproject.toml)
if [[ -n "$PY" ]]; then
  cd "$(dirname "$PY")" && uv sync -q 2>/dev/null
  SRC=$( [[ -d src ]] && echo src || echo . )
  tests=$(uv run pytest -q --cov --cov-report=term 2>&1)
  passed=$(grep -oE '[0-9]+ passed' <<<"$tests" | head -1); failed=$(grep -oE '[0-9]+ failed' <<<"$tests" | head -1)
  cov=$(grep -E '^TOTAL' <<<"$tests" | awk '{print $NF}')
  ruff=$(uv run ruff check . 2>&1 | grep -oE 'Found [0-9]+ error' | grep -oE '[0-9]+' || echo 0)
  mypy=$(uv run mypy --strict "$SRC" 2>&1 | grep -oE 'Found [0-9]+ error' | grep -oE '[0-9]+' || echo 0)
  loc=$(find "$SRC" -name '*.py' -not -path '*/.venv/*' -not -path '*/tests/*' -not -path '*/migrations/*' -exec cat {} + 2>/dev/null | grep -cvE '^\s*(#|$)')
  echo "API  · tests: ${passed:-0 passed}${failed:+, $failed} · coverage ${cov:-n/a} · ruff errors $ruff · mypy errors $mypy · $loc lines"
  API_ROW="| ${passed:-0 passed} | ${failed:-0 failed} | ${cov:-n/a} | $ruff | $mypy | $loc |"
fi

# ---- Web (Node) ------------------------------------------------------------------------
WEB_ROW="| n/a | n/a | n/a |"
PKG=$(find_one package.json)
if [[ -n "$PKG" ]]; then
  cd "$(dirname "$PKG")"
  if [[ -f package-lock.json ]]; then npm ci --silent >/dev/null 2>&1; else npm install --silent >/dev/null 2>&1; fi
  has() { python3 -c "import json,sys; d=json.load(open('package.json')); sys.exit(0 if '$1' in d.get('scripts',{}) else 1)"; }
  b=1; l=1; t=1
  has build && { npm run -s build >/dev/null 2>&1; b=$?; }
  has lint  && { npm run -s lint  >/dev/null 2>&1; l=$?; }
  if grep -q '"vitest"' package.json; then npx vitest run >/dev/null 2>&1; t=$?
  elif has test; then npm test --silent >/dev/null 2>&1; t=$?; fi
  echo "Web  · build $(ok $b) · lint $(ok $l) · tests $(ok $t)"
  WEB_ROW="| $(ok $b) | $(ok $l) | $(ok $t) |"
fi

# ---- Production files ------------------------------------------------------------------
cd "$P"
yes_no() { [[ -n "$1" ]] && echo "✅" || echo "❌"; }
readme=$(yes_no "$(find_one README.md)")
dockerfile=$(yes_no "$(find_one Dockerfile)")
compose=$(yes_no "$(find_one docker-compose.yml)$(find_one compose.yml)$(find_one docker-compose.yaml)")
ci=$(yes_no "$(find "$P" -path '*/.github/workflows/*.y*ml' -not -path '*/node_modules/*' | head -1)")
migrations=$(yes_no "$(find_one alembic.ini)")
envex=$(yes_no "$(find_one .env.example)")
echo "Files · README $readme · Dockerfile $dockerfile · compose $compose · CI $ci · migrations $migrations · .env.example $envex"

DOCK="not run"
if [[ "$DOCKER" == --docker ]]; then
  CF=$(find_one docker-compose.yml); [[ -z "$CF" ]] && CF=$(find_one compose.yml)
  if [[ -n "$CF" ]] && command -v docker >/dev/null; then
    (cd "$(dirname "$CF")" && docker compose config -q && docker compose build -q) >/dev/null 2>&1; DOCK=$(ok $?)
  else DOCK="❌ (no compose file or no docker)"; fi
  echo "Docker · compose build $DOCK"
fi

echo
echo "Rows for results.md:"
echo "API:   $API_ROW"
echo "Web:   $WEB_ROW"
echo "Files: | $readme | $dockerfile | $compose | $ci | $migrations | $envex | $DOCK |"
