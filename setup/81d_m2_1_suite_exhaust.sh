#!/usr/bin/env bash
# 81d_m2_1_suite_exhaust.sh — battery: exhaust (inject always) + invalid + reset
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_decision_policy
echo "loadavg: $(cat /proc/loadavg)"

echo "== battery: exhaust (inject always -> expect ERR_RECOVERY_EXHAUSTED) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh exhaust > "$E/61_C_exhausted.out" 2>&1
grep -E '"outcome"|ERR_RECOVERY_EXHAUSTED|RECOVERY:' "$E/61_C_exhausted.out" | head -6

echo "== battery: invalid target (expect typed IK fail) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh invalid > "$E/61_D_invalid.out" 2>&1
grep -E '"outcome"|"error_code"|IK' "$E/61_D_invalid.out" | head -5

echo "== battery: reset =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh reset > "$E/61_E_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/61_E_reset.out" | tail -1

echo "== decisions tail =="
tail -n 2 /home/ros/.ros/flexcell/decisions.jsonl
