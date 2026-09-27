#!/usr/bin/env bash
# 81a_m2_1_suite_start.sh — backup old battery evidence, start stack, run happy + recovery
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

W=/mnt/f/flexcell-stage/setup/acceptance/week15
E=$W/m2_1_decision_policy
B=$W/att_w15_20260926
CLI=/tmp/flexcell_cli
mkdir -p "$E" "$B"
tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"

echo "== backup original Week-1.5 battery evidence =="
cp $W/61_*.out "$B/" 2>/dev/null; cp "$W/61_summary.out" "$B/" 2>/dev/null
ls "$B" | wc -l | xargs echo "backed up files:"

echo "== managed start =="
{ echo "=== flexcell start | $(date -Is) ==="; t0=$(date +%s); bash "$CLI" start; rc=$?; t1=$(date +%s); echo "START_DURATION_S=$((t1-t0))"; echo "RC=$rc"; } > "$E/81a_start.out" 2>&1
grep -E "START OK|START FAILED|START_DURATION_S" "$E/81a_start.out"

echo "== health gate =="
{ echo "=== health strict | $(date -Is) ==="; bash "$CLI" health; echo "RC=$?"; } > "$E/81a_health.out" 2>&1
grep -c '"OK"' "$E/81a_health.out" | xargs echo "OK checks:"

echo "== battery: happy =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh happy > "$E/61_A_happy.out" 2>&1
grep -E '"outcome"|zone_a_error_m|zone_b_error_m|run_id' "$E/61_A_happy.out" | head -6

echo "== battery: recovery (inject once) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh recovery > "$E/61_B_recovery.out" 2>&1
grep -E '"outcome"|ERR_RECOVERY|RECOVERY|run_id' "$E/61_B_recovery.out" | head -8

echo "== decisions logged so far =="
grep -c '"action"' /home/ros/.ros/flexcell/decisions.jsonl 2>/dev/null | xargs echo "decision records:"
tail -n 2 /home/ros/.ros/flexcell/decisions.jsonl 2>/dev/null | head -2
