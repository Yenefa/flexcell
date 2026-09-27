#!/usr/bin/env bash
# 83e_invalid_regress.sh — Step 0 (#20) battery part 3:
# invalid-target re-run (needs pick to succeed so the unreachable PLACE pose
# surfaces the typed IK failure), reset-after-failure signature comparison
# vs original 61_E3, and the Day-2 MoveToPose regression (32).
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
C=src/flexcell/flexcell_skills/test/w1_client.py
mkdir -p "$E"

echo "== reset after failure: compare vs original 61_E3 signature =="
grep -oE '"ok": [a-z]*|"scene_cleared": [a-z]*' \
  /mnt/f/flexcell-stage/setup/acceptance/week15/61_E3_reset_after_failure.out 2>/dev/null | head -2

echo "== case D retry: invalid target (EXPECT typed IK failure at PLACE) =="
for i in 1 2; do
  bash "$CLI" reset > "$E/83e_reset_d$i.out" 2>&1
  {
    echo "=== 83e_invalid attempt $i | $(date -Is) | EXPECT: IK_UNREACHABLE at PLACE ==="
    timeout 120 python3 "$C" --action task --object target_box_a --pose 0.42 0 0.0175
    echo "RC=$?"
  } > "$E/83e_invalid_$i.out" 2>&1
  DET=$(grep -oE '"detail": "[^"]*"' "$E/83e_invalid_$i.out" | head -1)
  echo "attempt $i: $DET"
  if echo "$DET" | grep -q "IK\|UNREACHABLE"; then
    echo "INVALID_CASE_REACHED_IK: yes"
    break
  fi
  echo "-- pick starved again; settle 30s before retry --"
  sleep 30
done
grep -E '"outcome"|error_code' "$E/83e_invalid_$i.out" | head -3

echo "== Day-2 MoveToPose regression (32) =="
{ bash /mnt/f/flexcell-stage/setup/32_day2_acceptance.sh; echo "REGRESS_RC=$?"; } \
  > "$E/83e_day2_regress.out" 2>&1
tail -4 "$E/83e_day2_regress.out"
grep -c "MOTION_DETECTED=True" "$E/83e_day2_regress.out" | xargs echo "MOTION_DETECTED count:"

echo "== 83e DONE =="
