#!/usr/bin/env bash
# Scenario tests for skills/setup-project/scripts/taskgit.sh against throwaway repos
# with a local bare "origin". Each scenario reproduces a bug found during review.
#
# Run: bash tests/test_taskgit.sh            (all)
#      bash tests/test_taskgit.sh cr_wipe     (scenarios whose name contains "cr_wipe")
set -uo pipefail

TG="${TASKGIT_UNDER_TEST:-$(cd "$(dirname "$0")/.." && pwd)/skills/setup-project/scripts/taskgit.sh}"
FILTER=${1:-}
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
PASS=0; FAIL=0; FAILED=()
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

# ---- helpers ---------------------------------------------------------------------------
new_repo() {  # fresh origin + main checkout in $R with TASKS/STATE/DECISIONS and check.sh
  local d="$WORK/$1"; rm -rf "$d"; mkdir -p "$d"
  git init -q --bare -b main "$d/origin.git"
  git clone -q "$d/origin.git" "$d/proj" 2>/dev/null
  R="$d/proj"; ORIGIN="$d/origin.git"
  git -C "$R" checkout -q -b main 2>/dev/null || true
  mkdir -p "$R/scripts"
  printf '#!/bin/bash\n! grep -rq BROKEN --include=*.py .\n' > "$R/scripts/check.sh"
  printf '# Tasks\n- T-01: In progress\n- T-02: Backlog\n' > "$R/TASKS.md"
  printf '# State\nstage: build\n' > "$R/STATE.md"
  printf '# Decisions\n' > "$R/DECISIONS.md"
  echo "x = 1" > "$R/shared_code.py"
  git -C "$R" add -A && git -C "$R" commit -qm init && git -C "$R" push -q -u origin main 2>/dev/null
}
sedi() { local f="${*: -1}"; sed -i.bak "$@" && rm -f "$f.bak"; }   # sed -i that works with BSD sed (macOS)
tg() { bash "$TG" "$@"; }
tgq() { bash "$TG" "$@" >/dev/null 2>&1; }
on_main() { git -C "$R" show "origin/main:$1" 2>/dev/null; }
check() {  # check "<description>" <command...>
  local desc=$1; shift
  if "$@"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); FAILED+=("$SCEN: $desc"); echo "    ✗ $desc"; fi
}
expect_exit() { local want=$1; shift; "$@" >/dev/null 2>&1; local got=$?; [[ $got == "$want" ]] || { echo "      (exit $got, wanted $want)"; return 1; }; }
clean_main() { [[ -z "$(git -C "$R" status --porcelain --untracked-files=no)" ]] && [[ ! -f "$R/.git/MERGE_HEAD" ]]; }
contains() { grep -q -- "$2" <<<"$1"; }
scenario() { SCEN=$1; [[ -z "$FILTER" || "$SCEN" == *"$FILTER"* ]] || return 1; echo "• $SCEN"; return 0; }

# ---- scenarios -------------------------------------------------------------------------

if scenario cr_wipe_recorded_results; then
  # Reported bug: a task approved+recorded while CR-1 was open was wiped when CR-1 merged.
  new_repo cr1
  C=$(tg start "$R" CR-1)
  T=$(tg start "$R" T-01); echo "a = 1" > "$T/a.py"; tgq checkpoint "$R" T-01 "coder done"
  sedi 's/T-02: Backlog/T-02: Backlog (re-planned by CR-1)/; s/T-01: In progress/T-01: In progress (CR view)/' "$C/TASKS.md"
  echo "- CR-1 decision (should be reverted)" >> "$C/DECISIONS.md"
  tgq checkpoint "$R" CR-1 "re-plan"
  check "task approval is held while CR is open (exit 8)" expect_exit 8 tg approve "$R" T-01 "feat: a"
  check "main untouched by held approval" clean_main
  # simulate a record that slipped in on main anyway (e.g. from another device)
  sedi 's/T-01: In progress/T-01: Done/' "$R/TASKS.md"; echo "- D-01 T-01 decision" >> "$R/DECISIONS.md"
  tgq record "$R" "chore: record T-01"
  check "CR with conflicting TASKS.md aborts with exit 4" expect_exit 4 tg approve "$R" CR-1 "docs: CR-1"
  check "main still has T-01 Done" contains "$(on_main TASKS.md)" "T-01: Done"
  check "main still has the T-01 decision" contains "$(on_main DECISIONS.md)" "D-01 T-01 decision"
  check "main checkout clean after abort" clean_main
  check "CR branch kept for re-plan" test -d "$R-wt/CR-1"
  # planner redoes the re-plan on top of current main: sync gives conflict → reset TASKS.md to main + re-apply
  git -C "$C" fetch -q origin main && git -C "$C" merge -q -X theirs --no-edit origin/main >/dev/null 2>&1
  sedi 's/T-02: Backlog$/T-02: Backlog (re-planned by CR-1)/' "$C/TASKS.md"; tgq checkpoint "$R" CR-1 "re-plan on current main"
  check "CR merges after re-plan" expect_exit 0 tg approve "$R" CR-1 "docs: CR-1"
  m=$(on_main TASKS.md); d=$(on_main DECISIONS.md)
  check "T-01 Done survived the CR merge" contains "$m" "T-01: Done"
  check "CR re-plan landed" contains "$m" "re-planned by CR-1"
  check "T-01 decision survived" contains "$d" "D-01 T-01 decision"
  check "CR did not change DECISIONS.md" bash -c "! grep -q 'should be reverted' <<<'$d'"
  check "task approval unblocked after CR merged" expect_exit 0 tg approve "$R" T-01 "feat: a"
fi

if scenario cr_clean_merge_keeps_both; then
  new_repo cr2
  C=$(tg start "$R" CR-2); echo "- T-09: Backlog (new from CR-2)" >> "$C/TASKS.md"; echo "spec v2" > "$C/SPEC.md"
  tgq checkpoint "$R" CR-2 "docs"
  sedi 's/T-01: In progress/T-01: Done/' "$R/TASKS.md"; tgq record "$R" "chore: record"
  check "non-overlapping CR re-plan merges" expect_exit 0 tg approve "$R" CR-2 "docs: CR-2"
  m=$(on_main TASKS.md)
  check "keeps main's record" contains "$m" "T-01: Done"
  check "keeps CR's new task" contains "$m" "T-09: Backlog"
  check "CR's spec change landed" test "$(on_main SPEC.md)" = "spec v2"
fi

if scenario parallel_tasks_shared_files; then
  # Reported bug: two parallel tasks both edited TASKS.md; the second squash conflicted and left main in UU state.
  new_repo par
  A=$(tg start "$R" T-01); B=$(tg start "$R" T-02)
  echo "a = 1" > "$A/a.py"; sedi 's/T-01: In progress/T-01: Done/' "$A/TASKS.md"; tgq checkpoint "$R" T-01 x
  echo "b = 1" > "$B/b.py"; sedi 's/T-02: Backlog/T-02: Done/' "$B/TASKS.md"; tgq checkpoint "$R" T-02 x
  check "first approve" expect_exit 0 tg approve "$R" T-01 "feat: a"
  check "second approve" expect_exit 0 tg approve "$R" T-02 "feat: b"
  check "main clean, no conflict" clean_main
  check "both code files on main" test -n "$(on_main a.py)$(on_main b.py)"
  check "tasks did not change TASKS.md" contains "$(on_main TASKS.md)" "T-02: Backlog"
fi

if scenario record_missing_shared_file; then
  new_repo rec; git -C "$R" rm -q STATE.md; git -C "$R" commit -qm "no state"; git -C "$R" push -q 2>/dev/null
  sedi 's/T-01: In progress/T-01: Done/' "$R/TASKS.md"
  check "record works when STATE.md doesn't exist" expect_exit 0 tg record "$R" "chore: record"
  check "recorded on origin" contains "$(on_main TASKS.md)" "T-01: Done"
fi

if scenario code_conflict_between_tasks; then
  new_repo conf
  A=$(tg start "$R" T-03); B=$(tg start "$R" T-04)
  echo "x = 3" > "$A/shared_code.py"; tgq checkpoint "$R" T-03 x
  echo "x = 4" > "$B/shared_code.py"; tgq checkpoint "$R" T-04 x
  check "first approve" expect_exit 0 tg approve "$R" T-03 "feat: c"
  check "conflicting second approve exits 4" expect_exit 4 tg approve "$R" T-04 "feat: d"
  check "main clean after abort" clean_main
  check "T-04 branch kept" test -d "$R-wt/T-04"
fi

if scenario check_fails_after_sync; then
  new_repo chk; E=$(tg start "$R" T-05); echo "BROKEN = 1" > "$E/e.py"; tgq checkpoint "$R" T-05 x
  before=$(git -C "$R" rev-parse origin/main)
  check "approve exits 5 when check.sh fails" expect_exit 5 tg approve "$R" T-05 "feat: e"
  check "check output written to a file, not printed" test -s "$R-wt/T-05/.results/T-05/sync-check.txt"
  check "stderr carries only the path" bash -c "! bash '$TG' approve '$R' T-05 x 2>&1 | grep -q BROKEN"
  git -C "$R" fetch -q
  check "main unchanged" test "$(git -C "$R" rev-parse origin/main)" = "$before"
fi

if scenario stale_worktree_and_resume_from_origin; then
  new_repo stale; W=$(tg start "$R" T-06); echo "w = 1" > "$W/w.py"; echo "# progress" > "$W/TASK_PROGRESS.md"; tgq checkpoint "$R" T-06 "coder done"
  rm -rf "$W"
  check "start restores a deleted worktree" bash -c "[[ \$(bash '$TG' start '$R' T-06) == '$W' ]] && test -f '$W/w.py'"
  rm -rf "$W"; git -C "$R" worktree prune; git -C "$R" branch -q -D wip/T-06
  check "start resumes from origin when local branch is gone" bash -c "bash '$TG' start '$R' T-06 >/dev/null && test -f '$W/TASK_PROGRESS.md'"
fi

if scenario diverged_main; then
  new_repo div; F=$(tg start "$R" T-07); echo "f = 1" > "$F/f.py"; tgq checkpoint "$R" T-07 x
  echo local > "$R/local.txt"; git -C "$R" add local.txt; git -C "$R" commit -qm local
  git clone -q "$ORIGIN" "$WORK/other" 2>/dev/null; echo r > "$WORK/other/r.txt"
  git -C "$WORK/other" add r.txt; git -C "$WORK/other" commit -qm remote; git -C "$WORK/other" push -q 2>/dev/null; rm -rf "$WORK/other"
  check "approve exits 3 when local main diverged" expect_exit 3 tg approve "$R" T-07 "feat: f"
  check "worktree kept" test -d "$R-wt/T-07"
fi

if scenario leftover_merge_in_main; then
  new_repo lo; F=$(tg start "$R" T-08); echo "f = 1" > "$F/f.py"; tgq checkpoint "$R" T-08 x
  echo a > "$R/c.txt"; git -C "$R" add c.txt; git -C "$R" commit -qm ca; git -C "$R" push -q 2>/dev/null
  git -C "$R" checkout -q -b side HEAD~1; echo b > "$R/c.txt"; git -C "$R" add c.txt; git -C "$R" commit -qm cb
  git -C "$R" checkout -q main; git -C "$R" merge side >/dev/null 2>&1
  check "approve cleans a leftover conflicted merge and succeeds" expect_exit 0 tg approve "$R" T-08 "feat: f"
  check "main clean" clean_main
fi

if scenario push_rejected_then_retry; then
  new_repo push; G=$(tg start "$R" T-09); echo "g = 1" > "$G/g.py"; tgq checkpoint "$R" T-09 x
  printf '#!/bin/sh\nexit 1\n' > "$ORIGIN/hooks/pre-receive"; chmod +x "$ORIGIN/hooks/pre-receive"
  check "approve exits 7 when push is rejected" expect_exit 7 tg approve "$R" T-09 "feat: g"
  check "worktree kept after failed push" test -d "$R-wt/T-09"
  rm "$ORIGIN/hooks/pre-receive"
  check "re-run approve pushes the waiting commit" expect_exit 0 tg approve "$R" T-09 "feat: g"
  check "exactly one feat: g commit on origin" test "$(git -C "$R" log --oneline origin/main | grep -c 'feat: g')" = 1
  check "worktree cleaned up" test ! -d "$R-wt/T-09"
fi

if scenario secrets_blocked; then
  new_repo sec; S=$(tg start "$R" T-10); echo "KEY=1" > "$S/.env"
  check "checkpoint refuses .env (exit 2)" expect_exit 2 tg checkpoint "$R" T-10 x
  rm "$S/.env"; echo "KEY=" > "$S/.env.example"
  check ".env.example is fine" expect_exit 0 tg checkpoint "$R" T-10 x
fi

if scenario more_secret_files_blocked; then
  # T7: only .env/.pem/.key were blocked by name
  new_repo sec2; S2=$(tg start "$R" T-23)
  for f in credentials.json gcp/service-account-prod.json cert.p12 .ssh/id_ed25519 .npmrc kaggle.json .envrc .pypirc; do
    mkdir -p "$(dirname "$S2/$f")"; echo secret > "$S2/$f"
    check "checkpoint refuses $f (exit 2)" expect_exit 2 tg checkpoint "$R" T-23 x
    rm -f "$S2/$f"
  done
  echo '{}' > "$S2/package.json"; echo 'x' > "$S2/id_rsa.pub"
  check "ordinary files still commit" expect_exit 0 tg checkpoint "$R" T-23 x
fi

if scenario plan_owns_all_shared; then
  new_repo plan; P=$(tg start "$R" plan)
  printf '# Tasks\n- T-01: Backlog\n- T-02: Backlog\n- T-03: Backlog\n' > "$P/TASKS.md"; echo "- D-01 stack" >> "$P/DECISIONS.md"
  tgq checkpoint "$R" plan "tasks"
  check "plan approve" expect_exit 0 tg approve "$R" plan "chore: plan"
  check "plan's TASKS.md landed" contains "$(on_main TASKS.md)" "T-03: Backlog"
  check "plan's DECISIONS.md landed" contains "$(on_main DECISIONS.md)" "D-01 stack"
fi

if scenario scope_reverts_out_of_scope_files; then
  new_repo scope; W=$(tg start "$R" T-11); mkdir -p "$W/tests" "$W/src"
  echo "def test(): pass" > "$W/tests/test_x.py"; echo "hacked" >> "$W/shared_code.py"; echo "new" > "$W/src/sneaky.py"
  out=$(tg scope "$R" T-11 tester)
  check "reports reverted files" contains "$out" "REVERTED 2"
  check "test file kept" test -f "$W/tests/test_x.py"
  check "tracked file restored" test "$(cat "$W/shared_code.py")" = "x = 1"
  check "untracked out-of-scope file removed" test ! -e "$W/src/sneaky.py"
fi

if scenario scope_catches_committed_changes; then
  # S1: an agent that committed its own out-of-scope edit used to keep it ("scope: no changes").
  new_repo scopec; W=$(tg start "$R" T-12); tgq checkpoint "$R" T-12 "started"
  base=$(git -C "$W" rev-parse HEAD); mkdir -p "$W/tests"
  echo "hacked" >> "$W/shared_code.py"; echo "def test(): pass" > "$W/tests/test_y.py"
  git -C "$W" add -A && git -C "$W" commit -qm "agent commit"
  out=$(tg scope "$R" T-12 tester 2>&1)
  check "reports the committed out-of-scope file" contains "$out" "REVERTED 1"
  check "agent's commit undone" test "$(git -C "$W" rev-parse HEAD)" = "$base"
  check "committed edit reverted" test "$(cat "$W/shared_code.py")" = "x = 1"
  check "in-scope file kept" test -f "$W/tests/test_y.py"
  tgq checkpoint "$R" T-12 "tester done"
  check "checkpoint pushes only the in-scope change" test "$(git -C "$R" show "origin/wip/T-12:shared_code.py")" = "x = 1"
fi

if scenario start_installs_locked_deps; then
  # T1: node_modules/.venv are git-ignored, so fresh worktrees had no dependencies and coders can't install.
  new_repo deps; mkdir -p "$R/frontend" "$WORK/fakebin"
  echo '{}' > "$R/frontend/package-lock.json"; git -C "$R" add -A; git -C "$R" commit -qm lock; git -C "$R" push -q 2>/dev/null
  printf '#!/bin/sh\nmkdir -p node_modules && echo "$*" > node_modules/.installed\n' > "$WORK/fakebin/npm"; chmod +x "$WORK/fakebin/npm"
  D=$(PATH="$WORK/fakebin:$PATH" tg start "$R" T-13)
  check "start prints only the worktree path" test "$D" = "$R-wt/T-13"
  check "npm ci ran in frontend/" contains "$(cat "$D/frontend/node_modules/.installed" 2>/dev/null)" "ci"
  check "checkpoint still works after the install" expect_exit 0 tg checkpoint "$R" T-13 x
  D2=$(TASKGIT_SKIP_DEPS=1 PATH="$WORK/fakebin:$PATH" tg start "$R" T-14)
  check "TASKGIT_SKIP_DEPS=1 skips the install" test ! -e "$D2/frontend/node_modules"
  nonpm=$(tr ':' '
' <<<"$PATH" | while IFS= read -r d; do [[ -x "$d/npm" ]] || printf '%s:' "$d"; done)
  out=$(PATH="${nonpm%:}" bash "$TG" start "$R" T-15 2>&1 >/dev/null)
  check "a missing package manager is a warning, not an error" contains "$out" "npm not found"
fi

if scenario precommit_hook_does_not_block_checkpoints; then
  # T2: env-setup installs pre-commit into .git/hooks (shared by every worktree); WIP code fails it.
  new_repo hook; printf '#!/bin/sh\necho "lint failed" >&2\nexit 1\n' > "$R/.git/hooks/pre-commit"; chmod +x "$R/.git/hooks/pre-commit"
  cp "$R/.git/hooks/pre-commit" "$R/.git/hooks/pre-merge-commit"
  H=$(tg start "$R" T-16); echo "half_done = (" > "$H/wip.py"
  check "checkpoint succeeds despite a failing pre-commit hook" expect_exit 0 tg checkpoint "$R" T-16 "coder halfway"
  check "the WIP commit is on origin" test -n "$(git -C "$R" ls-remote origin wip/T-16)"
  echo "y = 2" > "$R/other.py"; git -C "$R" add other.py; git -C "$R" commit -q --no-verify -m other; git -C "$R" push -q 2>/dev/null
  echo "half_done = 1" > "$H/wip.py"; tgq checkpoint "$R" T-16 "coder done"
  check "sync merges main despite the hook" expect_exit 0 tg sync "$R" T-16
fi

if scenario recheck_when_origin_moves_during_approve; then
  # T5: when origin moved during approve, the rebased commit was pushed without running check.sh again
  race_hook() {  # race_hook <file> <content>: the first push of main is beaten by another clone
    cat > "$R/.git/hooks/pre-push" <<HOOK
#!/bin/sh
grep -q refs/heads/main || exit 0
[ -f "$WORK/race-$1" ] && exit 0
touch "$WORK/race-$1"
rm -rf "$WORK/race-clone"; git clone -q "$ORIGIN" "$WORK/race-clone" 2>/dev/null && cd "$WORK/race-clone" \
  && echo "$2" > "$1" && git add "$1" && git commit -qm "race $1" && git push -q origin main 2>/dev/null
exit 0
HOOK
    chmod +x "$R/.git/hooks/pre-push"
  }
  new_repo rc1; G=$(tg start "$R" T-20); echo "g = 1" > "$G/g.py"; tgq checkpoint "$R" T-20 x
  race_hook z.py "BROKEN = 1"
  check "approve stops when the new main fails the checks (exit 5)" expect_exit 5 tg approve "$R" T-20 "feat: g"
  check "the untested commit was not pushed" bash -c "! git -C '$R' log --oneline origin/main | grep -q 'feat: g'"
  check "worktree kept" test -d "$R-wt/T-20"
  new_repo rc2; H=$(tg start "$R" T-21); echo "h = 1" > "$H/h.py"; tgq checkpoint "$R" T-21 x
  race_hook other.txt "fine"
  check "a harmless race re-syncs, re-checks and pushes" expect_exit 0 tg approve "$R" T-21 "feat: h"
  check "origin has both changes" test -n "$(on_main other.txt)" -a -n "$(on_main h.py)"
  check "exactly one feat: h commit" test "$(git -C "$R" log --oneline origin/main | grep -c 'feat: h')" = 1
fi

if scenario conflicts_in_odd_names; then
  # T9: `for f in $conflicts` split names with spaces; shared names were regexes (TASKS.md matched TASKSxmd)
  new_repo odd2; printf 'a\n' > "$R/my notes.py"; printf 'a\n' > "$R/TASKSxmd"
  git -C "$R" add -A; git -C "$R" commit -qm odd; git -C "$R" push -q 2>/dev/null
  A=$(tg start "$R" T-24); printf 'mine\n' > "$A/my notes.py"; tgq checkpoint "$R" T-24 x
  printf 'theirs\n' > "$R/my notes.py"; git -C "$R" commit -qam theirs; git -C "$R" push -q 2>/dev/null
  out=$(bash "$TG" sync "$R" T-24 2>&1); code=$?
  check "conflict in 'my notes.py' reported as one file (exit 4)" test "$code" = 4
  check "the message names the whole file" contains "$out" "my notes.py"
  check "worktree not left mid-merge" test ! -f "$(git -C "$A" rev-parse --git-dir)/MERGE_HEAD"
  B=$(tg start "$R" T-25); printf 'b\n' > "$B/TASKSxmd"; tgq checkpoint "$R" T-25 x
  printf 'c\n' > "$R/TASKSxmd"; git -C "$R" commit -qam c; git -C "$R" push -q 2>/dev/null
  out=$(bash "$TG" sync "$R" T-25 2>&1)
  check "TASKSxmd is reported as a code conflict, not as the shared TASKS.md" contains "$out" "conflicts with main in: TASKSxmd"
  # record must refuse other modified files, including ones whose names the old regex matched
  printf 'd\n' > "$R/TASKSxmd"; sedi 's/T-01: In progress/T-01: Done/' "$R/TASKS.md"
  check "record refuses a modified TASKSxmd (exit 3)" expect_exit 3 tg record "$R" "chore: record"
fi

if scenario offline_cr_check_holds_approval; then
  # T10: with origin unreachable, ls-remote's error was hidden and approvals weren't held
  new_repo off; O=$(tg start "$R" T-26); echo "o = 1" > "$O/o.py"; tgq checkpoint "$R" T-26 x
  git -C "$R" remote set-url origin "$WORK/no-such-origin.git"
  out=$(bash "$TG" approve "$R" T-26 "feat: o" 2>&1); code=$?
  check "approve stops with exit 3 when origin can't be asked" test "$code" = 3
  check "the message says why" contains "$out" "change requests"
  check "main untouched" clean_main
  git -C "$R" remote set-url origin "$ORIGIN"
  check "approve works again once origin is back" expect_exit 0 tg approve "$R" T-26 "feat: o"
fi

if scenario start_warns_on_diverged_branch; then
  # T11: `merge --ff-only … || true` kept a diverged local branch without a word
  new_repo dv; V=$(tg start "$R" T-27); echo "v = 1" > "$V/v.py"; tgq checkpoint "$R" T-27 base
  git clone -q "$ORIGIN" "$WORK/dv-other" 2>/dev/null; git -C "$WORK/dv-other" checkout -q wip/T-27
  echo "phone = 1" > "$WORK/dv-other/phone.py"; git -C "$WORK/dv-other" add -A; git -C "$WORK/dv-other" commit -qm phone
  git -C "$WORK/dv-other" push -q origin wip/T-27 2>/dev/null
  echo "laptop = 1" > "$V/laptop.py"; git -C "$V" add -A; git -C "$V" commit -qm laptop   # local-only commit
  git -C "$R" worktree remove --force "$V"
  out=$(bash "$TG" start "$R" T-27 2>&1 >/dev/null)
  check "start warns about the divergence" contains "$out" "have diverged"
  check "and says which copy it kept" contains "$out" "Keeping the LOCAL copy"
  check "local work kept" test -f "$V/laptop.py"
  rm -rf "$WORK/dv-other"
fi

if scenario no_empty_commits; then
  # T12: --allow-empty made a commit and a push for every step, even when nothing changed
  new_repo empty; E2=$(tg start "$R" T-28); echo "e = 1" > "$E2/e.py"; tgq checkpoint "$R" T-28 "coder done"
  before=$(git -C "$E2" rev-list --count HEAD)
  out=$(tg checkpoint "$R" T-28 "reviewer done")
  check "a step that changed nothing makes no commit" test "$(git -C "$E2" rev-list --count HEAD)" = "$before"
  check "and says so" contains "$out" "nothing changed"
  check "the task still approves" expect_exit 0 tg approve "$R" T-28 "feat: e"
  check "no empty commit on main" test -n "$(git -C "$R" show --stat --format= origin/main)"
fi

if scenario approve_keeps_untracked_files; then
  # T6: the dirty check ignored untracked files, then `worktree remove --force` deleted them
  new_repo untr; U=$(tg start "$R" T-22); echo "u = 1" > "$U/u.py"; tgq checkpoint "$R" T-22 x
  echo "not yet checkpointed" > "$U/notes.py"
  check "approve refuses while a file isn't checkpointed (exit 3)" expect_exit 3 tg approve "$R" T-22 "feat: u"
  check "the untracked file survives" test -f "$U/notes.py"
  tgq checkpoint "$R" T-22 y
  check "approve works once it's checkpointed" expect_exit 0 tg approve "$R" T-22 "feat: u"
  check "the file reached main" test -n "$(on_main notes.py)"
fi

if scenario scope_handles_odd_file_names; then
  # S20: --porcelain quoted "my file.py" and "naïve.py", so scope checked and reverted the wrong names
  new_repo odd; echo "a = 1" > "$R/my code.py"; git -C "$R" add -A; git -C "$R" commit -qm odd; git -C "$R" push -q 2>/dev/null
  W=$(tg start "$R" T-19); mkdir -p "$W/tests" "$W/src"
  echo "changed" >> "$W/my code.py"; echo "x" > "$W/src/naïve file.py"; echo "def test(): pass" > "$W/tests/test ok.py"
  out=$(tg scope "$R" T-19 tester)
  check "reports both out-of-scope files" contains "$out" "REVERTED 2"
  check "tracked file with a space restored" test "$(cat "$W/my code.py")" = "a = 1"
  check "untracked non-ASCII file removed" test ! -e "$W/src/naïve file.py"
  check "in-scope file with a space kept" test -f "$W/tests/test ok.py"
fi

if scenario approve_and_reject_forget_agent_pins; then
  # S8: the scope guard pins each agent to its task worktree in .git/devteam-agents/; a finished task's
  # pins go with its worktree
  new_repo pins; P1=$(tg start "$R" T-29); P2=$(tg start "$R" T-30); P3=$(tg start "$R" T-31)
  mkdir -p "$R/.git/devteam-agents"
  echo "$P1" > "$R/.git/devteam-agents/agent-1"; echo "$P2" > "$R/.git/devteam-agents/agent-2"
  echo "$P3" > "$R/.git/devteam-agents/agent-3"
  echo "a = 1" > "$P1/a.py"; tgq checkpoint "$R" T-29 x
  check "approve works" expect_exit 0 tg approve "$R" T-29 "feat: a"
  check "approve removes the approved task's pins" test ! -e "$R/.git/devteam-agents/agent-1"
  tgq reject "$R" T-30
  check "reject removes the rejected task's pins" test ! -e "$R/.git/devteam-agents/agent-2"
  check "other tasks' pins stay" test -f "$R/.git/devteam-agents/agent-3"
fi

if scenario portable_to_macos; then
  # T3: macOS ships bash 3.2 and BSD tools: no mapfile/readarray, grep -P, stat -c, head -n -N, bare sed -i.
  code=$(grep -v '^ *#' "$TG")
  for bad in mapfile readarray 'grep -P' 'stat -c' 'head -n -' 'sed -i ' 'declare -A' 'local -n'; do
    check "taskgit.sh avoids '$bad'" bash -c '! grep -qF -- "$1" <<<"$2"' _ "$bad" "$code"
  done
  new_repo port; P=$(tg start "$R" T-17)
  check "usage text prints" contains "$(bash "$TG" 2>&1)" "taskgit.sh start"
  echo 'KEY=1' > "$P/.env.local"
  check ".env.local still blocked without grep -P" expect_exit 2 tg checkpoint "$R" T-17 x
  rm "$P/.env.local"; echo 'KEY=' > "$P/.env.example"
  check ".env.example still allowed" expect_exit 0 tg checkpoint "$R" T-17 x
fi

if scenario rebase_conflict_during_approve; then
  # T4: origin moved during approve with a conflicting change; the failed pull --rebase left main mid-rebase.
  new_repo rb; F=$(tg start "$R" T-18); echo "mine" > "$F/f.txt"; tgq checkpoint "$R" T-18 x
  # pre-push hook: the first time main is pushed, someone else pushes a conflicting f.txt first
  cat > "$R/.git/hooks/pre-push" <<HOOK
#!/bin/sh
grep -q refs/heads/main || exit 0
[ -f "$WORK/rb-raced" ] && exit 0
touch "$WORK/rb-raced"
git clone -q "$ORIGIN" "$WORK/rb-other" 2>/dev/null && cd "$WORK/rb-other" && echo theirs > f.txt && git add f.txt \
  && git commit -qm theirs && git push -q origin main 2>/dev/null
exit 0
HOOK
  chmod +x "$R/.git/hooks/pre-push"
  # (since T5 the retry re-syncs the task with the new main, which reports the conflict)
  check "approve reports the conflict with the new main (exit 4)" expect_exit 4 tg approve "$R" T-18 "feat: f"
  check "task branch kept for the owner agent" test -d "$R-wt/T-18"
  check "nothing of ours reached origin" bash -c "! git -C '$R' log --oneline origin/main | grep -q 'feat: f'"
  check "main checkout is not left mid-rebase" bash -c "[[ ! -d '$R/.git/rebase-merge' && ! -d '$R/.git/rebase-apply' ]]"
  check "main checkout clean" clean_main
  # a rebase left behind by a session that died: the next record clears it instead of failing confusingly
  rm -f "$R/.git/hooks/pre-push"; git -C "$R" reset -q --hard origin/main
  git -C "$R" checkout -q -b side; echo side > "$R/f.txt"; git -C "$R" commit -qam side; git -C "$R" checkout -q main
  git -C "$R" rebase side >/dev/null 2>&1 || true
  git -C "$R" checkout -q main 2>/dev/null; sedi 's/T-01: In progress/T-01: Done/' "$R/TASKS.md" 2>/dev/null
  tgq record "$R" "chore: record"
  check "record clears a leftover rebase" bash -c "[[ ! -d '$R/.git/rebase-merge' && ! -d '$R/.git/rebase-apply' ]]"
fi

if scenario timing_log; then
  # D10: every start, checkpoint, approve and reject leaves a line for bench.py's time per step
  new_repo timing
  T=$(tg start "$R" T-01); echo "a = 1" > "$T/a.py"
  tgq checkpoint "$R" T-01 "implement started"; tgq checkpoint "$R" T-01 "implement done"
  tgq approve "$R" T-01 "feat: a"
  tg start "$R" T-02 >/dev/null; tgq reject "$R" T-02
  LOG="$R/.git/devteam-timing.log"
  check "timing log exists in the main git dir" test -f "$LOG"
  check "checkpoint lines carry the step message" grep -q $'\tT-01\timplement started$' "$LOG"
  check "approve is logged once" test "$(grep -c $'\tT-01\tapproved$' "$LOG")" = 1
  check "reject is logged" grep -q $'\tT-02\trejected$' "$LOG"
  check "lines are timestamp, id, event" bash -c "awk -F'\t' 'NF!=3 || \$1 !~ /^20[0-9-]+T[0-9:]+Z\$/ {exit 1}' '$LOG'"
fi

# ---- summary ---------------------------------------------------------------------------
echo
echo "taskgit scenarios: $PASS passed, $FAIL failed"
# ${a[@]+...}: bash 3.2 (macOS) with set -u treats an empty array as unbound
for f in ${FAILED[@]+"${FAILED[@]}"}; do echo "  FAILED: $f"; done
(( FAIL == 0 ))
