#!/usr/bin/env bash
# Task branches + checkpoints for /setup-project.
# Each task (or planning stage) lives on its own branch wip/<id> in its own worktree
# at <repo>-wt/<id>, so parallel tasks never share a working tree, and every step is
# committed and pushed to wip/<id> so work survives a session ending mid-task.
# main only changes through `approve` (Jake approved the result card).
#
# Usage:
#   taskgit.sh start      <repo-dir> <id>                 create/restore worktree + branch, print its path
#   taskgit.sh checkpoint <repo-dir> <id> "<step msg>"    commit everything on wip/<id> and push it
#   taskgit.sh approve    <repo-dir> <id> "<commit msg>"  squash wip/<id> into main, push main, delete wip/<id>
#   taskgit.sh reject     <repo-dir> <id>                 delete wip/<id> (local + remote) and its worktree
#   taskgit.sh list       <repo-dir>                      list wip/* branches on origin with their last step
#   taskgit.sh diffstat   <repo-dir> <id>                 changes of wip/<id> vs main (for the result card)
set -euo pipefail

cmd=${1:?command}; repo=${2:?repo-dir}; repo=$(cd "$repo" && pwd)
wtroot="${repo}-wt"
main=$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#origin/##' || true)
main=${main:-main}
PROGRESS=TASK_PROGRESS.md

blocked_files() {  # refuse to commit secrets / results / big files
  local bad
  bad=$(git -C "$1" diff --cached --name-only | grep -E '(^|/)\.env$|(^|/)\.env\.[^e]|\.pem$|\.key$|^\.results/' || true)
  if [[ -n "$bad" ]]; then echo "BLOCKED: refusing to commit: $bad" >&2; exit 2; fi
  local big
  big=$(git -C "$1" diff --cached --name-only -z | xargs -0 -r -I{} find "$1/{}" -maxdepth 0 -type f -size +20M 2>/dev/null || true)
  if [[ -n "$big" ]]; then echo "BLOCKED: files over 20MB staged: $big" >&2; exit 2; fi
}

case "$cmd" in
  start)
    id=${3:?id}; wt="$wtroot/$id"; br="wip/$id"
    mkdir -p "$wtroot"
    git -C "$repo" fetch -q origin "$main" || true
    if [[ -d "$wt" ]]; then echo "$wt"; exit 0; fi
    if git -C "$repo" ls-remote --exit-code --heads origin "$br" >/dev/null 2>&1; then
      git -C "$repo" fetch -q origin "$br:$br" 2>/dev/null || git -C "$repo" fetch -q origin "$br"
      git -C "$repo" worktree add -q "$wt" "$br"           # resume an existing task
    elif git -C "$repo" show-ref --verify -q "refs/heads/$br"; then
      git -C "$repo" worktree add -q "$wt" "$br"
    else
      git -C "$repo" worktree add -q -b "$br" "$wt" "origin/$main" 2>/dev/null \
        || git -C "$repo" worktree add -q -b "$br" "$wt" "$main"
    fi
    echo "$wt"
    ;;
  checkpoint)
    id=${3:?id}; msg=${4:?step message}; wt="$wtroot/$id"
    git -C "$wt" add -A
    blocked_files "$wt"
    git -C "$wt" commit -q --allow-empty -m "wip($id): $msg"
    git -C "$wt" push -q -u origin "wip/$id" 2>&1 | grep -v -E '^(remote:|To |\s)' || true
    echo "checkpoint wip/$id: $msg"
    ;;
  approve)
    id=${3:?id}; msg=${4:?commit message}; wt="$wtroot/$id"; br="wip/$id"
    git -C "$repo" checkout -q "$main"
    git -C "$repo" pull -q --ff-only origin "$main" 2>/dev/null || true
    git -C "$repo" merge --squash "$br" >/dev/null
    git -C "$repo" rm -q --cached --ignore-unmatch "$PROGRESS" >/dev/null
    rm -f "$repo/$PROGRESS"
    blocked_files "$repo"
    git -C "$repo" commit -q -m "$msg"
    git -C "$repo" push -q origin "$main"
    git -C "$repo" worktree remove --force "$wt" 2>/dev/null || true
    git -C "$repo" branch -q -D "$br" 2>/dev/null || true
    git -C "$repo" push -q origin --delete "$br" 2>/dev/null || true
    git -C "$repo" log --oneline -1
    ;;
  reject)
    id=${3:?id}; wt="$wtroot/$id"; br="wip/$id"
    git -C "$repo" worktree remove --force "$wt" 2>/dev/null || true
    git -C "$repo" branch -q -D "$br" 2>/dev/null || true
    git -C "$repo" push -q origin --delete "$br" 2>/dev/null || true
    echo "rejected: removed $br"
    ;;
  list)
    git -C "$repo" fetch -q --prune origin
    for ref in $(git -C "$repo" for-each-ref --format='%(refname:short)' 'refs/remotes/origin/wip/'); do
      echo "${ref#origin/}  ·  $(git -C "$repo" log -1 --format='%s (%cr)' "$ref")"
    done
    ;;
  diffstat)
    id=${3:?id}
    git -C "$repo" diff --stat "$main...wip/$id" -- . ":(exclude)$PROGRESS"
    ;;
  *) echo "unknown command: $cmd" >&2; exit 1 ;;
esac
