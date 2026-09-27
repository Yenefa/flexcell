#!/usr/bin/env bash
# 69_git_delivery.sh — Week-1.5 delivery: verify ws repo, push, verify remote SHA, clean worktree
# Safety gates: HEAD must be 7956d63; worktree churn must be content-free
# (--ignore-cr-at-eol zero diff) before any restore. No force push, no rebase.
set -o pipefail

WS=/home/ros/agentic_workcell_ws
E=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
OUT="$E/69_git_delivery.out"

{
  echo "=== git delivery (ws repo) | $(date -Is) ==="
  cd "$WS" || exit 3
  HEAD_SHA=$(git rev-parse HEAD)
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  SHORT=$(git rev-parse --short=7 HEAD)
  echo "HEAD: $HEAD_SHA"
  echo "branch: $BRANCH"
  echo "remote: $(git remote get-url origin)"
  echo "--- porcelain (before) ---"
  git status --porcelain
  CHURN=$(git diff --ignore-cr-at-eol --stat | wc -l)
  echo "churn_stat_lines_ignoring_cr=$CHURN (0 = pure line-ending churn)"
  if [ "$SHORT" != "7956d63" ]; then
    echo "ABORT: unexpected HEAD $SHORT (expected 7956d63) — no push"
    exit 4
  fi
  echo "=== push origin HEAD:$BRANCH ==="
  GIT_TERMINAL_PROMPT=0 git push origin "HEAD:$BRANCH" 2>&1
  echo "push_rc=$?"
  echo "--- remote SHA after push ---"
  git ls-remote origin "refs/heads/$BRANCH"
  echo "--- worktree restore (only if content-free churn) ---"
  if [ "$CHURN" -eq 0 ] && [ -n "$(git status --porcelain)" ]; then
    git checkout -- .
    echo "restored line-ending churn to committed state"
  else
    echo "restore skipped (churn_stat_lines=$CHURN or tree already clean)"
  fi
  echo "--- porcelain (after) ---"
  git status --porcelain
  echo "porcelain_after_lines=$(git status --porcelain | wc -l)"
} > "$OUT" 2>&1

cat "$OUT"
