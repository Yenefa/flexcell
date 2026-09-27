#!/usr/bin/env bash
# 71_week2_commit.sh — copy Week-2 prep doc into ws repo and commit LOCALLY (no push)
set -o pipefail
SRC=/mnt/f/flexcell-stage/agentic_workcell_ws/docs/WEEK2_PREPARATION.md
WS=/home/ros/agentic_workcell_ws
OUT=/mnt/f/flexcell-stage/setup/71_week2_commit.out

{
  echo "=== week2 prep doc commit | $(date -Is) ==="
  cp "$SRC" "$WS/docs/WEEK2_PREPARATION.md" || exit 3
  cd "$WS" || exit 3
  git add docs/WEEK2_PREPARATION.md
  echo "--- staged ---"
  git status --porcelain
  git commit -m "Week-2 preparation: architecture recon + DecisionPolicy/WorldState/benchmark design + Jev feasibility (docs only)" -m "Baseline 7956d63 (Week-1.5 delivery, frozen); no runtime behavior touched. Issue #1 prerequisites: DecisionPolicy proposal, WorldState v2 freeze candidate, benchmark protocol, Jev feasibility (CONFIRMED shape, UNKNOWN details marked)."
  echo "commit_rc=$?"
  echo "--- log ---"
  git log --oneline -2
  echo "porcelain_after_lines=$(git status --porcelain | wc -l)"
  echo "NOT pushed (authorization scope: documentation only)"
} 2>&1 | tee "$OUT"

exit 0
