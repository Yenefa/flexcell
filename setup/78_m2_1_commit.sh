#!/usr/bin/env bash
# 78_m2_1_commit.sh — WSL repo: ff-sync docs from code-clone, then commit M2.1 code
set -o pipefail
WS=/home/ros/agentic_workcell_ws
CC=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone
OUT=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2/78_commit.out

{
  echo "=== M2.1 code commit | $(date -Is) ==="
  cd "$WS" || exit 3
  echo "--- ff-sync docs from code-clone ---"
  git fetch "$CC" refs/heads/main || exit 4
  git merge --ff-only FETCH_HEAD || exit 4
  git log --oneline -1
  echo "--- sync code from staging (F:) ---"
  cp -r /mnt/f/flexcell-stage/agentic_workcell_ws/src/flexcell/. src/flexcell/
  git add src/flexcell
  echo "--- staged ---"
  git status --porcelain
  git commit -m "M2.1: WorldState v2 contract (issue #3) - additive msgs + versioned canonical serializer + 13 tests" -m "WorldState.msg v2 (schema_version + executor-owned TaskContext), RobotStateSummary +gripper aperture, WorldObject +klass/pose_age_s, ZoneState +occupied_by; new TaskContext/Assignment/TaskConstraints/HistoryEntry msgs. flexcell_skills/canonical_state.py: WorldStateSchemaVersion=2 envelope, deterministic JSON (sort_keys, 9-decimal rounding, allow_nan=False), notes[] stripped per ADR-002 B1, version gate + structural validation. common.py adds sample_gz_pose_age (sample_gz_pose untouched). observe_server fills additive fields only; task_fsm_server.py UNTOUCHED - runtime acceptance: health 12 OK, happy demo SUCCEEDED 5.5/8.4mm (within baseline range, recovery semantics identical), live /observe envelope probe violations NONE. Evidence: acceptance/week15/m2_1_worldstate_v2/"
  echo "COMMIT_RC=$?"
  git log --oneline -2
  echo "HEAD=$(git rev-parse HEAD)"
  echo "porcelain=$(git status --porcelain | wc -l)"
} > "$OUT" 2>&1

tail -8 "$OUT"
