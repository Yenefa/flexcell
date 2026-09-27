#!/usr/bin/env bash
# 83h_regress_with_offhome_arm.sh — Day-2 regression in the historically
# passing shape: case10's all-joints |>0.05| check structurally fails when the
# arm sits at the all-zero reset home and the target joint1 is itself 0.0
# (delta=0.0028). Running it after a demo (arm parked over zone_2, joint1
# ~0.197) reproduces the 81-series passing verdict. start->health->reset->
# demo->regression->stop, one bounded run.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
C=src/flexcell/flexcell_skills/test/w1_client.py
mkdir -p "$E"
tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"

echo "== managed start =="
{ bash "$CLI" start; echo "RC=$?"; } > "$E/83h_start.out" 2>&1
grep -E "START OK|START FAILED" "$E/83h_start.out"

echo "== health gate =="
{ bash "$CLI" health; echo "RC=$?"; } > "$E/83h_health.out" 2>&1
echo "OK checks: $(grep -c '"OK"' "$E/83h_health.out")"

echo "== reset =="
{ bash "$CLI" reset; echo "RC=$?"; } > "$E/83h_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/83h_reset.out" | tail -1

echo "== happy demo (moves arm off the zero home) =="
timeout 170 python3 "$C" --action demo --scenario week1_demo_v1 > "$E/83h_demo.out" 2>&1
tail -n 1 /home/ros/.ros/flexcell/demo_runs.jsonl > "$E/83h_run.jsonl"
python3 - "$E/83h_run.jsonl" <<'PYEOF'
import json, sys
r = json.loads(open(sys.argv[1]).read().strip())
print('DEMO outcome=%s zone=(%.4f, %.4f)' % (r['outcome'], r['zone_a_error_m'], r['zone_b_error_m']))
PYEOF

echo "== Day-2 regression (arm off-home) =="
{ bash /mnt/f/flexcell-stage/setup/32_day2_acceptance.sh regression; echo "REGRESS_RC=$?"; } \
  > "$E/83h_day2_regress.out" 2>&1
grep -E "MOTION_DETECTED|RC=" "$E/83h_day2_regress.out" | head -3
grep -c "MOTION_DETECTED = True" "$E/83h_day2_regress.out" | xargs echo "MOTION_DETECTED_True count:"

echo "== clean stop =="
{ bash "$CLI" stop; echo "RC=$?"; } > "$E/83h_stop.out" 2>&1
grep -E "STOP OK|STOP INCOMPLETE" "$E/83h_stop.out"
echo "== 83h DONE =="
