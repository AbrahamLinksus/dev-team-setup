#!/usr/bin/env bash
# Quality numbers for a finished run: tests, coverage, lint, types, size.
# Run: bash bench/check_outcome.sh <path to the project the run built>
set -uo pipefail
P=${1:?project folder}; P=$(cd "$P" && pwd)
ROOT=$(dirname "$(find "$P" -name pyproject.toml -not -path '*/.venv/*' -not -path '*/node_modules/*' | head -1)")
[[ -d "$ROOT" ]] || { echo "No pyproject.toml under $P"; exit 1; }
cd "$ROOT" && uv sync -q 2>/dev/null
SRC=$( [[ -d src ]] && echo src || echo . )
tests=$(uv run pytest -q --cov --cov-report=term 2>&1)
passed=$(grep -oE '[0-9]+ passed' <<<"$tests" | head -1); failed=$(grep -oE '[0-9]+ failed' <<<"$tests" | head -1)
cov=$(grep -E '^TOTAL' <<<"$tests" | awk '{print $NF}')
ruff=$(uv run ruff check . 2>&1 | grep -oE 'Found [0-9]+ error' | grep -oE '[0-9]+' || echo 0)
mypy=$(uv run mypy --strict "$SRC" 2>&1 | grep -oE 'Found [0-9]+ error' | grep -oE '[0-9]+' || echo 0)
pyfiles=$(find "$SRC" -name '*.py' -not -path '*/.venv/*' | wc -l)
loc=$(find "$SRC" -name '*.py' -not -path '*/.venv/*' -not -path '*/tests/*' -exec cat {} + 2>/dev/null | grep -cvE '^\s*(#|$)')
readme=$( [[ -f "$P/README.md" || -f "$ROOT/README.md" ]] && echo yes || echo no )
echo "Tests: ${passed:-0 passed}${failed:+, $failed} · coverage ${cov:-n/a} · ruff errors $ruff · mypy errors $mypy"
echo "Code: $pyfiles .py files, $loc lines (excl. tests) · README: $readme"
echo
echo "| ${passed:-0} | ${failed:-0 failed} | ${cov:-n/a} | $ruff | $mypy | $loc | $readme |"
