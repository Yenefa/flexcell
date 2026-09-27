#!/usr/bin/env bash
# 81a2_m2_1_suite_fix.sh — rebuild after Observe_Result.evidence_id fix, restart stack,
# rerun happy + recovery cases
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

W=/mnt/f/flexcell-stage/setup/acceptance/week15
E=$W/m2_1_decision_policy
CLI=/tmp/flexcell_cli

echo "== rebuild =="
cp -r /mnt/f/flexcell-stage/agentic_workcell_ws/src/flexcell/. src/flexcell/
colcon build --symlink-install --packages-select flexcell_interfaces flexcell_skills 2>&1 | tail -3
source install/setup.bash

echo "== restart stack (old processes hold the pre-fix module) =="
{ echo "=== flexcell stop | $(date -Is) ==="; bash "$CLI" stop; echo "RC=$?"; } > "$E/81a2_stop.out" 2>&1
grep -E "STOP OK|STOP INCOMPLETE" "$E/81a2_stop.out"
{ echo "=== flexcell start | $(date -Is) ==="; t0=$(date +%s); bash "$CLI" start; rc=$?; t1=$(date +%s); echo "START_DURATION_S=$((t1-t0))"; echo "RC=$rc"; } > "$E/81a2_start.out" 2>&1
grep -E "START OK|START FAILED|START_DURATION_S" "$E/81a2_start.out"

echo "== battery: happy (rerun) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh happy > "$E/61_A_happy.out" 2>&1
grep -E '"outcome"|zone_a_error_m|zone_b_error_m|run_id|"detail"' "$E/61_A_happy.out" | head -8

echo "== battery: recovery (rerun) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh recovery > "$E/61_B_recovery.out" 2>&1
grep -E '"outcome"|ERR_RECOVERY|RECOVERY|run_id' "$E/61_B_recovery.out" | head -8

echo "== decisions logged =="
wc -l /home/ros/.ros/flexcell/decisions.jsonl | xargs echo "decision records:"
tail -n 1 /home/ros/.ros/flexcell/decisions.jsonl
