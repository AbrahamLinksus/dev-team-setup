#!/usr/bin/env bash
# Task branches, checkpoints and approvals for /setup-project.
#
# Model:
#   - main (the main checkout at <repo>) changes only through `approve` and `record`.
#   - each task / planning stage lives on branch wip/<id> in worktree <repo>-wt/<id>;
#     every step is committed + pushed there (`checkpoint`), so work survives the session ending.
#   - Shared files (TASKS.md, STATE.md, DECISIONS.md) belong to main: tasks never change
#     them (checkpoint reverts any change); the Orchestrator updates them on main with
#     `record` after `approve`. Exceptions: `plan` and `CR-<n>` branches (approve with --keep-shared).
#   - Before a result card is shown, `sync` merges the latest main into the task branch
#     and re-runs scripts/check.sh, so a task is always tested against current main.
#
# Usage:
#   taskgit.sh start      <repo> <id>                    create/restore worktree; prints its path
#   taskgit.sh checkpoint <repo> <id> "<step msg>"       commit all on wip/<id>, push
#   taskgit.sh scope      <repo> <id> <agent>            revert files <agent> may not change (prints them)
#   taskgit.sh sync       <repo> <id>                    merge origin/main into wip/<id>, run check.sh, push
#   taskgit.sh diff       <repo> <id>                    full diff vs main (for the reviewer)
#   taskgit.sh diffstat   <repo> <id>                    diff --stat vs main (for the result card)
#   taskgit.sh approve    <repo> <id> "<msg>" [--keep-shared]   sync, squash into main, push, clean up
#   taskgit.sh record     <repo> "<msg>"                 commit + push shared-file updates on main
#   taskgit.sh reject     <repo> <id>                    drop wip/<id> (local + remote) and its worktree
#   taskgit.sh list       <repo>                         open wip/* branches on origin + last step
# Exit codes: 0 ok · 1 usage · 2 blocked files · 3 main not clean/diverged · 4 merge conflict
#             5 check.sh failed after sync · 6 squash failed · 7 committed locally but not pushed
set -uo pipefail

SHARED=(TASKS.md STATE.md DECISIONS.md)
PROGRESS=TASK_PROGRESS.md
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/../../../hooks/scope_guard.py"

die() { local code=$1; shift; printf 'TASKGIT ERROR: %b\n' "$*" >&2; exit "$code"; }
usage() { sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1 >&2; exit 1; }

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
  bad=$(git -C "$1" diff --cached --name-only | grep -P '(^|/)\.env$|(^|/)\.env\.(?!example$)|\.pem$|\.key$|^\.results/' || true)
  [[ -n "$bad" ]] && { git -C "$1" reset -q; die 2 "refusing to commit secrets/results: $bad"; }
  local f big=""
  while IFS= read -r f; do
    [[ -f "$1/$f" ]] && (( $(stat -c %s "$1/$f") > 20971520 )) && big+="$f "
  done < <(git -C "$1" diff --cached --name-only)
  [[ -n "$big" ]] && { git -C "$1" reset -q; die 2 "files over 20MB staged: $big"; }
  return 0
}

owns_shared() { [[ "$id" == plan || "$id" == CR-* ]]; }  # planning / change-request branches may edit shared files

ensure_wt() {  # sets wt; fails if the worktree doesn't exist
  wt="$wtroot/$id"; [[ -d "$wt" ]] || die 1 "no worktree for $id; run: taskgit.sh start $repo $id"
}

revert_shared_in_wt() {  # tasks may not change main-owned files
  local f changed=""
  for f in "${SHARED[@]}"; do
    if ! gw diff --quiet "origin/$main" -- "$f" 2>/dev/null; then
      gw checkout -q "origin/$main" -- "$f" 2>/dev/null || gw rm -q --cached --ignore-unmatch "$f" >/dev/null
      changed+="$f "
    fi
  done
  [[ -n "$changed" ]] && echo "note: reverted main-owned files changed in the task: $changed (the Orchestrator updates them on main with 'record')" >&2
  return 0
}

do_sync() {  # merge origin/main into wip/<id>, run check.sh; uses $id $wt
  g fetch -q origin "$main" || die 3 "fetch failed"
  if gw merge-base --is-ancestor "origin/$main" HEAD; then
    echo "sync: wip/$id already contains main@$(g rev-parse --short "origin/$main")"
  else
    if ! gw merge -q --no-edit "origin/$main" >/dev/null 2>&1; then
      local conflicts other
      conflicts=$(gw diff --name-only --diff-filter=U)
      other=$(echo "$conflicts" | grep -v -x -E "$(IFS='|'; echo "${SHARED[*]}|$PROGRESS")" || true)
      if [[ -n "$other" ]]; then
        gw merge --abort 2>/dev/null
        die 4 "wip/$id conflicts with main in: $(echo $other). Merge aborted; the task branch is unchanged. Send it to the owner agent/debugger to rebase onto main."
      fi
      for f in $conflicts; do
        if [[ "$f" == "$PROGRESS" ]] || owns_shared; then gw checkout -q --ours -- "$f"; else gw checkout -q --theirs -- "$f"; fi
        gw add -- "$f"
      done
      gw commit -q --no-edit || { gw merge --abort; die 4 "could not complete merge of main into wip/$id"; }
    fi
    echo "sync: merged main@$(g rev-parse --short "origin/$main") into wip/$id"
  fi
  if [[ -x "$wt/scripts/check.sh" || -f "$wt/scripts/check.sh" ]] && [[ "${TASKGIT_SKIP_CHECK:-0}" != 1 ]]; then
    local out
    if ! out=$(cd "$wt" && bash scripts/check.sh 2>&1); then
      echo "$out" | tail -40 >&2
      push_branch "$wt" "wip/$id" || true
      die 5 "scripts/check.sh fails on wip/$id after syncing with main (output above). Not approved."
    fi
    echo "sync: scripts/check.sh ✅ on wip/$id + current main"
  fi
  push_branch "$wt" "wip/$id" || echo "warning: could not push wip/$id" >&2
}

case "$cmd" in
  start)
    id=${3:?id}; wt="$wtroot/$id"; br="wip/$id"
    mkdir -p "$wtroot"
    g worktree prune                                   # forget worktrees whose folder was deleted
    g fetch -q origin "$main" 2>/dev/null || true
    if [[ -d "$wt" ]] && gw rev-parse --git-dir >/dev/null 2>&1; then echo "$wt"; exit 0; fi
    [[ -e "$wt" ]] && die 1 "$wt exists but is not a worktree; move it away first"
    if g ls-remote --exit-code --heads origin "$br" >/dev/null 2>&1; then
      g fetch -q origin "+$br:refs/remotes/origin/$br"
      if g show-ref --verify -q "refs/heads/$br"; then
        g worktree add -q "$wt" "$br" || die 1 "worktree add failed"
        gw merge -q --ff-only "origin/$br" 2>/dev/null || true
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
    echo "$wt"
    ;;

  checkpoint)
    id=${3:?id}; msg=${4:?step message}; ensure_wt
    owns_shared || revert_shared_in_wt
    gw add -A
    blocked_files "$wt"
    gw commit -q --allow-empty -m "wip($id): $msg" || die 1 "commit failed"
    push_branch "$wt" "wip/$id" || die 7 "checkpoint committed locally but NOT pushed (see error above)"
    echo "checkpoint wip/$id: $msg"
    ;;

  scope)
    id=${3:?id}; agent=${4:?agent}; ensure_wt
    [[ -f "$GUARD" ]] || die 1 "scope guard not found at $GUARD"
    mapfile -t changed < <(gw status --porcelain --untracked-files=all | sed -E 's/^.. //; s/.* -> //')
    (( ${#changed[@]} == 0 )) && { echo "scope: no changes"; exit 0; }
    mapfile -t bad < <(python3 "$GUARD" --check "$agent" "$wt" "${changed[@]}")
    if (( ${#bad[@]} == 0 )); then echo "scope: ${#changed[@]} changed file(s), all within $agent's scope"; exit 0; fi
    for f in "${bad[@]}"; do
      if gw ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then gw checkout -q HEAD -- "$f"; else rm -rf -- "$wt/$f"; fi
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
    id=${3:?id}; msg=${4:?commit message}; keep_shared=${5:-}; ensure_wt; br="wip/$id"
    # 1. main checkout must be clean and on main
    [[ -f "$repo/.git/MERGE_HEAD" ]] && { g merge --abort 2>/dev/null || g reset -q --merge; echo "note: aborted a leftover merge in the main checkout" >&2; }
    dirty=$(g status --porcelain --untracked-files=no)
    [[ -n "$dirty" ]] && die 3 "main checkout has uncommitted changes, approve stopped:\n$dirty\n(commit them with 'record' or discard them first)"
    g checkout -q "$main" || die 3 "cannot check out $main"
    g fetch -q origin "$main" || die 3 "fetch failed"
    g merge -q --ff-only "origin/$main" 2>/dev/null || die 3 "local $main has diverged from origin/$main; nothing was approved. Resolve: git -C $repo log --oneline origin/$main..$main"
    if [[ -n "$(g rev-list "origin/$main..$main")" ]]; then   # approved earlier but the push failed
      push_branch "$repo" "$main" || die 7 "local $main still has unpushed approved commits; fix the push first"
      echo "note: pushed previously approved local commits" >&2
    fi
    # 2. task branch must contain current main and pass check.sh
    do_sync
    excl=(":(exclude)$PROGRESS"); owns_shared || for f in "${SHARED[@]}"; do excl+=(":(exclude)$f"); done
    if g diff --quiet "$main" "$br" -- . "${excl[@]}"; then   # nothing left to merge: already on main
      g worktree remove --force "$wt" 2>/dev/null || true; g branch -q -D "$br" 2>/dev/null || true
      g push -q origin --delete "$br" 2>/dev/null || true; g worktree prune
      echo "approved: $id was already on $main ($(g log --oneline -1)); cleaned up"; exit 0
    fi
    gw diff --quiet && gw diff --cached --quiet || die 3 "wip/$id has uncommitted changes; checkpoint first"
    # 3. squash into main
    if ! g merge -q --squash "$br" >/dev/null 2>&1; then
      g reset -q --merge 2>/dev/null || g reset -q --hard HEAD
      die 6 "squash of $br into $main failed; main restored to $(g rev-parse --short HEAD)"
    fi
    if [[ "$keep_shared" != --keep-shared ]] && ! owns_shared; then
      for f in "${SHARED[@]}"; do
        if g cat-file -e "HEAD:$f" 2>/dev/null; then g checkout -q HEAD -- "$f"; else g rm -q --cached --ignore-unmatch "$f" >/dev/null; fi
      done
    fi
    g rm -q --cached --ignore-unmatch "$PROGRESS" >/dev/null; rm -f "$repo/$PROGRESS"
    blocked_files "$repo"
    g commit -q --allow-empty -m "$msg" || { g reset -q --hard HEAD; die 6 "commit on $main failed; main restored"; }
    # 4. push (one rebase retry if origin moved in the meantime)
    if ! push_branch "$repo" "$main"; then
      if g pull -q --rebase origin "$main" && push_branch "$repo" "$main"; then
        echo "note: origin/$main moved during approve; rebased and pushed" >&2
      else
        die 7 "approved commit $(g rev-parse --short HEAD) is on local $main but NOT pushed. Worktree and $br were kept. Fix the push, then re-run approve."
      fi
    fi
    # 5. clean up only after a successful push
    g worktree remove --force "$wt" 2>/dev/null || true
    g branch -q -D "$br" 2>/dev/null || true
    g push -q origin --delete "$br" 2>/dev/null || true
    g worktree prune
    echo "approved: $(g log --oneline -1)"
    ;;

  record)
    msg=${3:?commit message}
    g checkout -q "$main" || die 3 "cannot check out $main"
    present=(); for f in "${SHARED[@]}"; do [[ -e "$repo/$f" ]] || g cat-file -e "HEAD:$f" 2>/dev/null && present+=("$f"); done
    (( ${#present[@]} )) || { echo "record: no shared files present"; exit 0; }
    SHARED=("${present[@]}")
    other=$(g status --porcelain --untracked-files=no | sed -E 's/^.. //' | grep -v -x -E "$(IFS='|'; echo "${SHARED[*]}")" || true)
    [[ -n "$other" ]] && die 3 "record only commits ${SHARED[*]}; other files are modified on $main: $other"
    g diff --quiet -- "${SHARED[@]}" && { echo "record: nothing to record"; exit 0; }
    g fetch -q origin "$main" || die 3 "fetch failed"
    if ! g merge-base --is-ancestor "origin/$main" HEAD; then
      g stash push -q -- "${SHARED[@]}" || die 3 "stash failed"
      g merge -q --ff-only "origin/$main" || { g stash pop -q; die 3 "local $main diverged from origin"; }
      g stash pop -q || die 4 "shared files changed on origin too; resolve the conflict in ${SHARED[*]} on $main, then re-run record"
    fi
    g add -- "${SHARED[@]}"
    g commit -q -m "$msg" || die 1 "commit failed"
    push_branch "$repo" "$main" || { g pull -q --rebase origin "$main" && push_branch "$repo" "$main"; } \
      || die 7 "recorded commit is local only; NOT pushed"
    echo "recorded: $(g log --oneline -1)"
    ;;

  reject)
    id=${3:?id}; wt="$wtroot/$id"; br="wip/$id"
    g worktree remove --force "$wt" 2>/dev/null || true
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
