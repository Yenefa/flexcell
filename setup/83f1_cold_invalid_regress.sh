#!/usr/bin/env bash
# 83f1_cold_invalid_regress.sh — Step 0 (#20) re-run after host-sleep killed
# the stack (health timeout + action unavailable at 07:27UTC; DDS graph gone).
# Cold: stop -> (VM terminated externally) -> start -> health -> reset ->
# invalid retry -> Day-2 regress. Stack stays up for 83f2.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
C=src/flexcell/flexcell_skills/test/w1_client.py
mkdir -p "$E"
tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"

echo "== managed start =="
{ t0=$(date +%s); bash "$CLI" start; rc=$?; t1=$(date +%s);
  echo "START_DURATION_S=$((t1-t0))"; echo "RC=$rc"; } > "$E/83f1_start.out" 2>&1
grep -E "START OK|START FAILED|START_DURATION_S" "$E/83f1_start.out"

echo "== health gate =="
{ bash "$CLI" health; echo "RC=$?"; } > "$E/83f1_health.out" 2>&1
echo "OK checks: $(grep -c '"OK"' "$E/83f1_health.out")"

echo "== canonical reset =="
{ bash "$CLI" reset; echo "RC=$?"; } > "$E/83f1_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/83f1_reset.out" | tail -1

echo "== case D: invalid target (retry up to 3, expect typed IK failure at PLACE) =="
for i in 1 2 3; do
  bash "$CLI" reset > "$E/83f1_reset_d$i.out" 2>&1
  {
    echo "=== 83f1_invalid attempt $i | $(date -Is) ==="
    timeout 120 python3 "$C" --action task --object target_box_a --pose 0.42 0 0.0175
    echo "RC=$?"
  } > "$E/83f1_invalid_$i.out" 2>&1
  DET=$(grep -oE '"detail": "[^"]*"' "$E/83f1_invalid_$i.out" | head -1)
  echo "attempt $i: ${DET:-<no detail>}"
  if echo "$DET" | grep -q "IK\|UNREACHABLE"; then
    echo "INVALID_CASE_REACHED_IK: yes"
    break
  fi
  [ "$i" != "3" ] && sleep 30
done
grep -E '"outcome"|error_code' "$E/83f1_invalid_$i.out" | head -3

echo "== Day-2 MoveToPose regression (32) =="
{ bash /mnt/f/flexcell-stage/setup/32_day2_acceptance.sh; echo "REGRESS_RC=$?"; } \
  > "$E/83f1_day2_regress.out" 2>&1
tail -3 "$E/83f1_day2_regress.out"
grep -c "MOTION_DETECTED=True" "$E/83f1_day2_regress.out" | xargs echo "MOTION_DETECTED count:"

echo "== 83f1 DONE (stack stays up for 83f2) =="
