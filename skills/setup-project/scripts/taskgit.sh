#!/usr/bin/env bash
# Task branches, checkpoints and approvals for /setup-project.
#
# Model:
#   - main (the main checkout at <repo>) changes only through `approve` and `record`.
#   - each task / planning stage lives on branch wip/<id> in worktree <repo>-wt/<id>;
#     every step is committed + pushed there (`checkpoint`), so work survives the session ending.
#   - Shared files (TASKS.md, STATE.md, DECISIONS.md) belong to main: branches never change
#     them (checkpoint reverts any change); the Orchestrator updates them on main with
#     `record` after `approve`. Exceptions: `plan` owns all three (nothing runs in parallel
#     with planning); `CR-<n>` owns only TASKS.md (its re-plan). If TASKS.md changed on main
#     since the CR branched, sync/approve abort (exit 4) so the planner re-plans on current main.
#   - While a CR branch is open, task approvals are held (exit 8) so nothing is recorded
#     on main underneath the re-plan.
#   - Before a result card is shown, `sync` merges the latest main into the task branch
#     and re-runs scripts/check.sh, so a task is always tested against current main.
#
# Usage:
#   taskgit.sh start      <repo> <id>                    create/restore worktree, install locked deps
#                                                        (uv/npm/pnpm/yarn; TASKGIT_SKIP_DEPS=1 skips); prints its path
#   taskgit.sh checkpoint <repo> <id> "<step msg>"       commit all on wip/<id>, push
#   taskgit.sh scope      <repo> <id> <agent>            revert files <agent> may not change (prints them)
#   taskgit.sh sync       <repo> <id>                    merge origin/main into wip/<id>, run check.sh, push
#   taskgit.sh diff       <repo> <id>                    full diff vs main (for the reviewer)
#   taskgit.sh diffstat   <repo> <id>                    diff --stat vs main (for the result card)
#   taskgit.sh approve    <repo> <id> "<msg>"            sync, squash into main, push, clean up
#   taskgit.sh record     <repo> "<msg>"                 commit + push shared-file updates on main
#   taskgit.sh reject     <repo> <id>                    drop wip/<id> (local + remote) and its worktree
#   taskgit.sh undo       <repo> <id>                    revert an approved task's commit on main and push
#   taskgit.sh list       <repo>                         open wip/* branches on origin + last step
# Exit codes: 0 ok · 1 usage · 2 blocked files · 3 main not clean/diverged · 4 merge conflict
#             5 check.sh failed after sync · 6 squash failed · 7 committed locally but not pushed
#             8 approval held: a change request is open
set -uo pipefail

SHARED=(TASKS.md STATE.md DECISIONS.md)
PROGRESS=TASK_PROGRESS.md
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/../../../hooks/scope_guard.py"

die() { local code=$1; shift; printf 'TASKGIT ERROR: %b\n' "$*" >&2; exit "$code"; }
usage() { sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//' | sed '$d' >&2; exit 1; }
# Portable to macOS: its /bin/bash is 3.2 (no mapfile) and its tools are BSD (no grep -P, stat -c).
read_lines() {  # read_lines <array-name> < input: one array element per line
  local __line; eval "$1=()"
  while IFS= read -r __line || [[ -n "$__line" ]]; do eval "$1+=(\"\$__line\")"; done
}
file_size() { wc -c < "$1" | tr -d ' '; }

cmd=${1:-}; [[ -z "$cmd" ]] && usage
repo=${2:-}; [[ -z "$repo" ]] && usage
[[ -d "$repo/.git" || -f "$repo/.git" ]] || die 1 "$repo is not a git checkout"
repo=$(cd "$repo" && pwd); wtroot="${repo}-wt"
main=$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')
main=${main:-main}

g()  { git -C "$repo" "$@"; }
gw() { git -C "$wt" "$@"; }

push_branch() {  # push_branch <dir> <branch>; quiet on success
  local out; out=$(git -C "$1" push -u origin "$2" 2>&1) || { echo "$out" >&2; return 1; }
}

blocked_files() {
  local bad
  # secrets by file name (also cloud/SSH/registry credentials); check.sh scans contents (gitleaks)
  bad=$(git -C "$1" diff --cached --name-only | grep -E '(^|/)\.env(\..+)?$|(^|/)\.envrc$|\.pem$|\.key$|\.p12$|\.pfx$|(^|/)credentials\.json$|(^|/)service[-_]?account[^/]*\.json$|(^|/)id_(rsa|dsa|ecdsa|ed25519)$|(^|/)\.(npmrc|pypirc|netrc)$|(^|/)kaggle\.json$|^\.results/' \
        | grep -Ev '(^|/)\.env\.example$' || true)
  [[ -n "$bad" ]] && { git -C "$1" reset -q; die 2 "refusing to commit secrets/results: $bad"; }
  local f big=""
  while IFS= read -r f; do
    [[ -f "$1/$f" ]] && (( $(file_size "$1/$f") > 20971520 )) && big+="$f "
  done < <(git -C "$1" diff --cached --name-only)
  [[ -n "$big" ]] && { git -C "$1" reset -q; die 2 "files over 20MB staged: $big"; }
  return 0
}

owned_shared() {  # shared files this branch may change
  case "$id" in plan) echo "${SHARED[@]}" ;; CR-*) echo TASKS.md ;; *) echo "" ;; esac
}
is_owned() { local s; for s in $(owned_shared); do [[ "$s" == "$1" ]] && return 0; done; return 1; }
is_shared() { local s; for s in "${SHARED[@]}"; do [[ "$s" == "$1" ]] && return 0; done; return 1; }
open_crs() {  # open change-request branches (local or on origin); fails if origin can't be asked
  local remote
  # a failed ls-remote (offline, auth) used to look like "no CRs" and let approvals through
  remote=$(g ls-remote --heads origin 'wip/CR-*' 2>&1) || { printf '%s\n' "$remote" >&2; return 1; }
  { g for-each-ref --format='%(refname:short)' 'refs/heads/wip/CR-*'
    printf '%s\n' "$remote" | sed -n 's#.*refs/heads/##p'; } | sort -u
}

clear_leftovers() {  # a merge or rebase left half-done in the main checkout (e.g. a session died mid-approve)
  local gd; gd=$(g rev-parse --absolute-git-dir)
  if [[ -d "$gd/rebase-merge" || -d "$gd/rebase-apply" ]]; then
    g rebase --abort 2>/dev/null || rm -rf "$gd/rebase-merge" "$gd/rebase-apply"
    echo "note: aborted a leftover rebase in the main checkout" >&2
  fi
  if [[ -f "$gd/MERGE_HEAD" ]]; then
    g merge --abort 2>/dev/null || g reset -q --merge
    echo "note: aborted a leftover merge in the main checkout" >&2
  fi
  return 0
}

pull_rebase_main() {  # origin moved under us: replay local main on it; on a conflict undo the rebase
  g pull -q --rebase origin "$main" >/dev/null 2>&1 && return 0
  g rebase --abort 2>/dev/null || true
  return 1
}

unpin_agents() {  # forget the agent pins (scope guard) of the worktree being removed; uses $id
  local d f line
  d="$(g rev-parse --absolute-git-dir)/devteam-agents"
  [[ -d "$d" ]] || return 0
  for f in "$d"/*; do
    [[ -f "$f" ]] || continue
    IFS= read -r line < "$f" || true
    case "$line" in *-wt/"$id"|*-wt\\"$id") rm -f "$f" ;; esac
  done
  return 0
}

log_time() {  # D10: one line per event, read by bench.py for time per step; never fails the command
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$id" "$1" \
    >> "$(g rev-parse --absolute-git-dir 2>/dev/null)/devteam-timing.log" 2>/dev/null || true
}

ensure_wt() {  # sets wt; fails if the worktree doesn't exist
  wt="$wtroot/$id"; [[ -d "$wt" ]] || die 1 "no worktree for $id; run: taskgit.sh start $repo $id"
}

# The commit the current agent step started from. Every commit taskgit makes on wip/<id>
# (start, checkpoint, sync) moves it; `scope` compares the worktree against it, so edits an
# agent committed itself are still checked (and its own commits undone). Kept in the
# worktree's private git dir, which agents may not write.
step_base_file() { echo "$(gw rev-parse --absolute-git-dir)/devteam-step-base"; }
mark_step_base() { gw rev-parse HEAD > "$(step_base_file)"; }

revert_shared_in_wt() {  # branches may not change main-owned files they don't own
  local f changed=""
  for f in "${SHARED[@]}"; do
    is_owned "$f" && continue
    if ! gw diff --quiet "origin/$main" -- "$f" 2>/dev/null; then
      gw checkout -q "origin/$main" -- "$f" 2>/dev/null || gw rm -q --cached --ignore-unmatch "$f" >/dev/null
      changed+="$f "
    fi
  done
  [[ -n "$changed" ]] && echo "note: reverted main-owned files changed in the task: $changed (the Orchestrator updates them on main with 'record')" >&2
  return 0
}

install_deps() {  # install locked dependencies into a new worktree; uses $id $wt
  # .venv and node_modules are git-ignored, so a fresh worktree has none, and coders may not
  # install anything themselves. Lockfiles are already approved, so installing them is not Tier 1.
  [[ "${TASKGIT_SKIP_DEPS:-0}" == 1 ]] && return 0
  local log lock dir failed=""
  local -a run
  log="$(gw rev-parse --absolute-git-dir)/devteam-deps.log"; : > "$log"
  while IFS= read -r lock; do
    dir=$(dirname "$lock")
    case "$(basename "$lock")" in
      # every worktree installs the same lockfile, so the package managers' shared caches
      # (uv's and pnpm's global cache/store, npm's and yarn's download cache) already hold
      # everything after the first worktree; --prefer-offline uses them without asking the
      # registry again. uv links from its cache by default and needs no flag.
      uv.lock)           run=(uv sync --frozen) ;;
      package-lock.json) run=(npm ci --prefer-offline --no-audit --no-fund) ;;
      pnpm-lock.yaml)    run=(pnpm install --frozen-lockfile --prefer-offline) ;;
      yarn.lock)         run=(yarn install --frozen-lockfile --prefer-offline) ;;
      *) continue ;;
    esac
    if ! command -v "${run[0]}" >/dev/null 2>&1; then failed+="$dir (${run[0]} not found) "; continue; fi
    echo "\$ cd $dir && ${run[*]}" >> "$log"
    (cd "$wt/$dir" && "${run[@]}") >> "$log" 2>&1 < /dev/null || failed+="$dir "
  done < <(cd "$wt" && find . -maxdepth 3 \( -name node_modules -o -name .venv -o -name .git \) -prune -o \
             \( -name uv.lock -o -name package-lock.json -o -name pnpm-lock.yaml -o -name yarn.lock \) -print | sort)
  [[ -n "$failed" ]] && echo "warning: installing dependencies failed in: $failed(log: $log). Checks will fail in this worktree until that's fixed; give the log to env-setup." >&2
  return 0
}

do_sync() {  # merge origin/main into wip/<id>, run check.sh; uses $id $wt
  g fetch -q origin "$main" || die 3 "fetch failed"
  if gw merge-base --is-ancestor "origin/$main" HEAD; then
    echo "sync: wip/$id already contains main@$(g rev-parse --short "origin/$main")"
  else
    if ! gw merge -q --no-edit --no-verify "origin/$main" >/dev/null 2>&1; then
      # NUL-separated names in an array (names may contain spaces), and exact string
      # comparisons instead of the shared-file names used as a regex (TASKS.md matched TASKSxmd)
      local conflicts=() other=() f
      while IFS= read -r -d '' f; do conflicts+=("$f"); done < <(gw diff -z --name-only --diff-filter=U)
      if (( ${#conflicts[@]} == 0 )); then
        gw merge --abort 2>/dev/null
        die 4 "merging main into wip/$id failed without a content conflict (e.g. an untracked file would be overwritten). Merge aborted; the task branch is unchanged."
      fi
      for f in "${conflicts[@]}"; do [[ "$f" == "$PROGRESS" ]] || is_shared "$f" || other+=("$f"); done
      if (( ${#other[@]} )); then
        gw merge --abort 2>/dev/null
        die 4 "wip/$id conflicts with main in: ${other[*]}. Merge aborted; the task branch is unchanged. Send it to the owner agent/debugger to rebase onto main."
      fi
      for f in "${conflicts[@]}"; do
        if [[ "$f" == "$PROGRESS" ]]; then gw checkout -q --ours -- "$f"
        elif is_shared "$f" && ! is_owned "$f"; then gw checkout -q --theirs -- "$f"   # main's records win
        elif [[ "$id" == plan ]]; then gw checkout -q --ours -- "$f"
        else
          gw merge --abort 2>/dev/null
          die 4 "$f changed on main while $id was open (e.g. a task was recorded). Merge aborted; nothing on main was touched. Have the planner redo the re-plan of $f on top of current main, then checkpoint and approve again."
        fi
        gw add -- "$f"
      done
      gw commit -q --no-edit --no-verify || { gw merge --abort; die 4 "could not complete merge of main into wip/$id"; }
    fi
    echo "sync: merged main@$(g rev-parse --short "origin/$main") into wip/$id"
  fi
  mark_step_base
  # check.sh already passed on this exact tree (same commit tree, nothing uncommitted)?
  # Then skip it: sync before the card and sync inside approve otherwise run it twice on
  # identical code. Kept in the worktree's private git dir, which agents can't write.
  local pass_file tree="" clean=0
  pass_file="$(gw rev-parse --absolute-git-dir)/devteam-check-pass"
  if [[ -z "$(gw status --porcelain)" ]]; then clean=1; tree=$(gw rev-parse 'HEAD^{tree}'); fi
  if (( clean )) && [[ -f "$pass_file" && "$(cat "$pass_file")" == "$tree" ]]; then
    echo "sync: scripts/check.sh ✅ (passed earlier on this exact tree; not re-run)"
  elif [[ -x "$wt/scripts/check.sh" || -f "$wt/scripts/check.sh" ]] && [[ "${TASKGIT_SKIP_CHECK:-0}" != 1 ]]; then
    local out
    rm -f "$pass_file"
    if ! out=$(cd "$wt" && bash scripts/check.sh 2>&1); then
      mkdir -p "$wt/.results/$id"; printf '%s\n' "$out" > "$wt/.results/$id/sync-check.txt"
      push_branch "$wt" "wip/$id" || true
      die 5 "scripts/check.sh fails on wip/$id after syncing with main. Output: $wt/.results/$id/sync-check.txt (give that path to the debugger). Not approved."
    fi
    echo "sync: scripts/check.sh ✅ on wip/$id + current main"
    # only a clean tree is cached: uncommitted files could have changed what passed
    if (( clean )) && [[ -z "$(gw status --porcelain)" ]]; then printf '%s\n' "$tree" > "$pass_file"; fi
  fi
  push_branch "$wt" "wip/$id" || echo "warning: could not push wip/$id" >&2
}

case "$cmd" in
  start)
    id=${3:?id}; wt="$wtroot/$id"; br="wip/$id"
    log_time "start"
    mkdir -p "$wtroot"
    g worktree prune                                   # forget worktrees whose folder was deleted
    g fetch -q origin "$main" 2>/dev/null || true
    if [[ -d "$wt" ]] && gw rev-parse --git-dir >/dev/null 2>&1; then
      [[ -f "$(step_base_file)" ]] || mark_step_base
      echo "$wt"; exit 0
    fi
    [[ -e "$wt" ]] && die 1 "$wt exists but is not a worktree; move it away first"
    if g ls-remote --exit-code --heads origin "$br" >/dev/null 2>&1; then
      g fetch -q origin "+$br:refs/remotes/origin/$br"
      if g show-ref --verify -q "refs/heads/$br"; then
        g worktree add -q "$wt" "$br" || die 1 "worktree add failed"
        if ! gw merge -q --ff-only "origin/$br" 2>/dev/null; then
          # say so instead of silently keeping one copy. Local wins: it may hold checkpoints that
          # never reached origin, while origin's commits stay safe on origin.
          ahead=$(gw rev-list --count "origin/$br..HEAD"); behind=$(gw rev-list --count "HEAD..origin/$br")
          if (( behind > 0 )); then
            echo "warning: local $br and origin/$br have diverged ($ahead local-only, $behind origin-only commit(s)," \
                 "e.g. work from another device). Keeping the LOCAL copy. To take origin's instead:" \
                 "git -C $wt reset --hard origin/$br" >&2
          fi
        fi
      else
        g worktree add -q -b "$br" "$wt" "origin/$br" || die 1 "worktree add failed"
      fi
      gw branch -q --set-upstream-to="origin/$br" 2>/dev/null || true
    elif g show-ref --verify -q "refs/heads/$br"; then
      g worktree add -q "$wt" "$br" || die 1 "worktree add failed"
    else
      g worktree add -q -b "$br" "$wt" "origin/$main" 2>/dev/null || g worktree add -q -b "$br" "$wt" "$main" \
        || die 1 "worktree add failed"
    fi
    install_deps
    mark_step_base
    echo "$wt"
    ;;

  checkpoint)
    id=${3:?id}; msg=${4:?step message}; ensure_wt
    log_time "$msg"
    revert_shared_in_wt
    gw add -A
    blocked_files "$wt"
    # --no-verify: work in progress may not pass the project's pre-commit hooks yet (lint, auto-fixers
    # that rewrite files mid-commit); approve runs scripts/check.sh before anything reaches main.
    # no empty commits; a step that changed nothing needs no commit (the push below still
    # retries anything an earlier checkpoint couldn't push)
    if gw diff --cached --quiet; then
      mark_step_base
      push_branch "$wt" "wip/$id" || die 7 "nothing new to commit, but earlier checkpoints are NOT pushed (see error above)"
      echo "checkpoint wip/$id: $msg (nothing changed, no commit)"
      exit 0
    fi
    gw commit -q --no-verify -m "wip($id): $msg" || die 1 "commit failed"
    mark_step_base
    push_branch "$wt" "wip/$id" || die 7 "checkpoint committed locally but NOT pushed (see error above)"
    echo "checkpoint wip/$id: $msg"
    ;;

  scope)
    id=${3:?id}; agent=${4:?agent}; ensure_wt
    [[ -f "$GUARD" ]] || die 1 "scope guard not found at $GUARD"
    # An agent that commits its own edits would hide them from `git status`: undo any commit
    # made since the step started (keeping its changes in the worktree) so they are checked too.
    base=$(cat "$(step_base_file)" 2>/dev/null || true)
    if [[ -n "$base" && "$(gw rev-parse HEAD)" != "$base" ]]; then
      gw cat-file -e "$base^{commit}" 2>/dev/null || die 1 "step base $base for $id is missing; checkpoint again"
      n=$(gw rev-list --count "$base..HEAD" 2>/dev/null || echo "?")
      gw reset -q "$base" || die 1 "could not undo commits the agent made on wip/$id"
      echo "scope: undid $n commit(s) the agent made itself; their changes are checked below" >&2
    fi
    # -z: plain --porcelain quotes names with spaces or non-ASCII characters ("my file.py"), which
    # then matched nothing; -z gives raw names, and a rename's old name as a second entry.
    changed=(); rename_src=0
    while IFS= read -r -d '' entry; do
      if (( rename_src )); then changed+=("$entry"); rename_src=0; continue; fi
      changed+=("${entry:3}")
      [[ "${entry:0:1}" == [RC] ]] && rename_src=1
    done < <(gw -c core.quotepath=off status --porcelain -z --untracked-files=all)
    (( ${#changed[@]} == 0 )) && { echo "scope: no changes"; exit 0; }
    read_lines bad < <(PYTHONIOENCODING=utf-8 python3 "$GUARD" --check "$agent" "$wt" "${changed[@]}" | tr -d '\r')
    if (( ${#bad[@]} == 0 )); then echo "scope: ${#changed[@]} changed file(s), all within $agent's scope"; exit 0; fi
    for f in "${bad[@]}"; do
      if gw ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then gw checkout -q HEAD -- "$f"; else rm -rf -- "${wt:?}/$f"; fi
    done
    echo "scope: REVERTED ${#bad[@]} file(s) outside $agent's scope: ${bad[*]}"
    exit 0
    ;;

  sync)
    id=${3:?id}; ensure_wt; do_sync ;;

  diff)
    id=${3:?id}; g fetch -q origin "$main" 2>/dev/null || true
    g diff "origin/$main...wip/$id" -- . ":(exclude)$PROGRESS" ;;

  diffstat)
    id=${3:?id}; g fetch -q origin "$main" 2>/dev/null || true
    g diff --stat "origin/$main...wip/$id" -- . ":(exclude)$PROGRESS" ;;

  approve)
    id=${3:?id}; msg=${4:?commit message}; ensure_wt; br="wip/$id"
    if [[ -z "${TASKGIT_APPROVE_RETRY:-}" ]]; then log_time "approved"; fi
    if [[ "$id" != plan && "$id" != CR-* ]]; then
      crs=$(open_crs) || die 3 "can't reach origin to check for open change requests (see the error above); nothing was approved. Retry when origin is reachable."
      crs=$(printf '%s' "$crs" | tr '\n' ' ')
      [[ -n "${crs// }" ]] && die 8 "approvals are held while a change request is open ($crs). Merge or cancel it first; $id stays queued."
    fi
    # 1. main checkout must be clean and on main
    clear_leftovers
    dirty=$(g status --porcelain --untracked-files=no)
    [[ -n "$dirty" ]] && die 3 "main checkout has uncommitted changes, approve stopped:\n$dirty\n(commit them with 'record' or discard them first)"
    g checkout -q "$main" || die 3 "cannot check out $main"
    g fetch -q origin "$main" || die 3 "fetch failed"
    g merge -q --ff-only "origin/$main" 2>/dev/null || die 3 "local $main has diverged from origin/$main; nothing was approved. Resolve: git -C $repo log --oneline origin/$main..$main"
    if [[ -n "$(g rev-list "origin/$main..$main")" ]]; then   # approved earlier but the push failed
      push_branch "$repo" "$main" || die 7 "local $main still has unpushed approved commits; fix the push first"
      echo "note: pushed previously approved local commits" >&2
    fi
    # 2. task branch must contain current main and pass check.sh. Nothing may be left uncommitted:
    #    `worktree remove --force` below would delete it, untracked files included.
    left=$(gw status --porcelain --untracked-files=normal)
    [[ -n "$left" ]] && die 3 "wip/$id has changes that aren't checkpointed (approve would delete them):\n$left\nCheckpoint first (after the scope check), or remove them."
    do_sync
    excl=(":(exclude)$PROGRESS"); for f in "${SHARED[@]}"; do is_owned "$f" || excl+=(":(exclude)$f"); done
    if g diff --quiet "$main" "$br" -- . "${excl[@]}"; then   # nothing left to merge: already on main
      unpin_agents; g worktree remove --force "$wt" 2>/dev/null || true; g branch -q -D "$br" 2>/dev/null || true
      g push -q origin --delete "$br" 2>/dev/null || true; g worktree prune
      echo "approved: $id was already on $main ($(g log --oneline -1)); cleaned up"; exit 0
    fi
    # 3. squash into main
    if ! g merge -q --squash "$br" >/dev/null 2>&1; then
      g reset -q --merge 2>/dev/null || g reset -q --hard HEAD
      die 6 "squash of $br into $main failed; main restored to $(g rev-parse --short HEAD)"
    fi
    for f in "${SHARED[@]}"; do   # keep main's version of every shared file the branch doesn't own
      is_owned "$f" && continue
      if g cat-file -e "HEAD:$f" 2>/dev/null; then g checkout -q HEAD -- "$f"; else g rm -q --cached --ignore-unmatch "$f" >/dev/null; rm -f "$repo/$f"; fi
    done
    g rm -q --cached --ignore-unmatch "$PROGRESS" >/dev/null; rm -f "$repo/$PROGRESS"
    blocked_files "$repo"
    if g diff --cached --quiet; then   # never an empty commit on main
      g reset -q --hard HEAD
      die 6 "the squash of $br into $main is empty (the task only changed files main owns, or nothing at all); main restored. Reject the task, or record the shared-file changes on main with 'record'."
    fi
    # the Task: trailer lets `undo` find exactly this commit later (autopilot approvals)
    g commit -q -m "$msg" -m "Task: $id" || { g reset -q --hard HEAD; die 6 "commit on $main failed; main restored"; }
    # 4. push. If origin moved in the meantime, a rebased commit would reach main untested:
    #    drop our squash commit and run the whole approve once more, so the task is synced with the
    #    new main and scripts/check.sh runs again before anything is pushed.
    if ! push_branch "$repo" "$main"; then
      g fetch -q origin "$main" 2>/dev/null
      if [[ -n "$(g rev-list "$main..origin/$main" 2>/dev/null)" && "${TASKGIT_APPROVE_RETRY:-0}" != 1 ]]; then
        g reset -q --hard HEAD~1
        echo "note: origin/$main moved during approve; re-syncing $id with it and re-running the checks" >&2
        TASKGIT_APPROVE_RETRY=1 exec bash "$0" approve "$repo" "$id" "$msg"
      fi
      die 7 "approved commit $(g rev-parse --short HEAD) is on local $main but NOT pushed. Worktree and $br were kept. Fix the push, then re-run approve."
    fi
    # 5. clean up only after a successful push
    unpin_agents; g worktree remove --force "$wt" 2>/dev/null || true
    g branch -q -D "$br" 2>/dev/null || true
    g push -q origin --delete "$br" 2>/dev/null || true
    g worktree prune
    echo "approved: $(g log --oneline -1)"
    ;;

  record)
    msg=${3:?commit message}
    clear_leftovers
    g checkout -q "$main" || die 3 "cannot check out $main"
    present=(); for f in "${SHARED[@]}"; do [[ -e "$repo/$f" ]] || g cat-file -e "HEAD:$f" 2>/dev/null && present+=("$f"); done
    (( ${#present[@]} )) || { echo "record: no shared files present"; exit 0; }
    SHARED=("${present[@]}")
    modified=$(g -c core.quotepath=off status --porcelain --untracked-files=no | sed -E 's/^.. //' \
            | grep -v -x -F -f <(printf '%s\n' "${SHARED[@]}") || true)
    [[ -n "$modified" ]] && die 3 "record only commits ${SHARED[*]}; other files are modified on $main: $modified"
    g diff --quiet -- "${SHARED[@]}" && { echo "record: nothing to record"; exit 0; }
    g fetch -q origin "$main" || die 3 "fetch failed"
    if ! g merge-base --is-ancestor "origin/$main" HEAD; then
      g stash push -q -- "${SHARED[@]}" || die 3 "stash failed"
      g merge -q --ff-only "origin/$main" || { g stash pop -q; die 3 "local $main diverged from origin"; }
      g stash pop -q || die 4 "shared files changed on origin too; resolve the conflict in ${SHARED[*]} on $main, then re-run record"
    fi
    g add -- "${SHARED[@]}"
    g commit -q -m "$msg" || die 1 "commit failed"
    push_branch "$repo" "$main" || { pull_rebase_main && push_branch "$repo" "$main"; } \
      || die 7 "recorded commit is local only; NOT pushed (if origin/$main changed the same lines, the rebase was undone: the main checkout is clean, not mid-rebase)"
    echo "recorded: $(g log --oneline -1)"
    ;;

  undo)
    # an auto-approved task the owner doesn't want after all. Reverts its squash commit (found by
    # the "Task: <id>" trailer approve writes) with a new commit on main; history is never rewritten.
    id=${3:?id}
    [[ "$(g rev-parse --abbrev-ref HEAD)" == "$main" ]] || die 3 "the main checkout isn't on $main; nothing was undone"
    dirty=$(g status --porcelain --untracked-files=no)
    [[ -z "$dirty" ]] || die 3 "main checkout has uncommitted changes; nothing was undone:\n$dirty"
    g fetch -q origin "$main" || die 3 "fetch failed; nothing was undone"
    g merge -q --ff-only "origin/$main" 2>/dev/null || die 3 "local $main has diverged from origin/$main; nothing was undone"
    # git's own --grep, no `| grep -q` / `| head`: under pipefail a reader that exits early can
    # SIGPIPE git and turn a match into a failure (flaky on macOS CI)
    sha=$(g log -n 1 --format=%H --grep="^Task: $id\$" "$main")
    [[ -n "$sha" ]] || die 1 "no approved commit for $id on $main (looked for a 'Task: $id' trailer)"
    if [[ -n "$(g log -n 1 --format=%H --grep="^Undone: $id\$" "$sha..$main")" ]]; then
      die 1 "$id was already undone on $main"
    fi
    if ! g revert --no-commit "$sha" >/dev/null 2>&1; then
      g revert --abort 2>/dev/null; g reset -q --hard HEAD 2>/dev/null
      die 4 "can't undo $id cleanly: later approved work changed the same lines. Nothing changed. Undo the later task first, or make the change as a new task."
    fi
    g commit -q -m "Revert \"$(g log -n 1 --format=%s "$sha")\"" -m "This reverts commit $sha." -m "Undone: $id" \
      || { g reset -q --hard HEAD; die 6 "the revert commit for $id failed; main restored"; }
    log_time "undone"
    push_branch "$repo" "$main" || { g reset -q --hard HEAD~1; die 7 "the revert of $id couldn't be pushed; it was dropped again, so main is unchanged"; }
    echo "undone: $(g log --oneline -1)"
    ;;

  reject)
    id=${3:?id}; wt="$wtroot/$id"; br="wip/$id"
    log_time "rejected"
    unpin_agents; g worktree remove --force "$wt" 2>/dev/null || true
    g worktree prune
    g branch -q -D "$br" 2>/dev/null || true
    g push -q origin --delete "$br" 2>/dev/null || true
    echo "rejected: removed $br"
    ;;

  list)
    g fetch -q --prune origin 2>/dev/null || true
    found=0
    while IFS= read -r ref; do
      [[ -z "$ref" ]] && continue; found=1
      echo "${ref#origin/}  ·  $(g log -1 --format='%s (%cr)' "$ref")"
    done < <(g for-each-ref --format='%(refname:short)' 'refs/remotes/origin/wip/')
    (( found )) || echo "no open wip branches"
    ;;

  *) usage ;;
esac
