#!/usr/bin/env bash
# 83g_clean_regress.sh — Day-2 regression on a CLEAN scene.
# 83f2 ran case10 directly after the invalid case aborted MID-CARRY; the known
# hardening gap (reset does not clear attached collision objects) left a ghost
# attached box in the planning scene, which explains MOTION_DETECTED=False.
# This run: start -> health -> reset (clean) -> regression -> stop.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
mkdir -p "$E"
tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"

echo "== managed start =="
{ bash "$CLI" start; echo "RC=$?"; } > "$E/83g_start.out" 2>&1
grep -E "START OK|START FAILED" "$E/83g_start.out"

echo "== health gate =="
{ bash "$CLI" health; echo "RC=$?"; } > "$E/83g_health.out" 2>&1
echo "OK checks: $(grep -c '"OK"' "$E/83g_health.out")"

echo "== canonical reset (clean scene) =="
{ bash "$CLI" reset; echo "RC=$?"; } > "$E/83g_reset.out" 2>&1
grep -oE '"ok": [a-z]*|"scene_cleared": [a-z]*' "$E/83g_reset.out" | tail -2

echo "== Day-2 regression (clean scene) =="
{ bash /mnt/f/flexcell-stage/setup/32_day2_acceptance.sh regression; echo "REGRESS_RC=$?"; } \
  > "$E/83g_day2_regress.out" 2>&1
grep -E "MOTION_DETECTED|RC=" "$E/83g_day2_regress.out" | head -3
grep -c "MOTION_DETECTED = True" "$E/83g_day2_regress.out" | xargs echo "MOTION_DETECTED_True count:"

echo "== clean stop =="
{ bash "$CLI" stop; echo "RC=$?"; } > "$E/83g_stop.out" 2>&1
grep -E "STOP OK|STOP INCOMPLETE" "$E/83g_stop.out"
echo "== 83g DONE =="
