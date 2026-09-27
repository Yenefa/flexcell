#!/usr/bin/env bash
# 72_week2_ratify_commit.sh — copy ratified Week-2 prep doc into ws repo, commit locally
set -o pipefail
SRC=/mnt/f/flexcell-stage/agentic_workcell_ws/docs/WEEK2_PREPARATION.md
WS=/home/ros/agentic_workcell_ws
OUT=/mnt/f/flexcell-stage/setup/72_week2_ratify_commit.out

{
  echo "=== week2 ratification merge commit | $(date -Is) ==="
  cp "$SRC" "$WS/docs/WEEK2_PREPARATION.md" || exit 3
  cd "$WS" || exit 3
  git add docs/WEEK2_PREPARATION.md
  git commit -m "Week-2 prep ratified: merge chief decisions (c)1-6" -m "Versioned policy-input serialization (WorldStateSchemaVersion), FSMPolicy parity priority raised, LLM deferred until interface+runner+replay, JevBackend abstraction (TypeSafe|Local), threshold sweep {0.5,0.7,0.9} as experimental variable, S7 kept in primary. Implementation order fixed: WorldState > Decision Interface > FSMPolicy > Scenario Replay > Jev > LLM."
  echo "commit_rc=$?"
  git log --oneline -3
  echo "porcelain_after_lines=$(git status --porcelain | wc -l)"
  echo "HEAD=$(git rev-parse HEAD)"
} 2>&1 | tee "$OUT"

exit 0
