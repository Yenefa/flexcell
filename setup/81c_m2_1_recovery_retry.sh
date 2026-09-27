#!/usr/bin/env bash
# 81c_m2_1_recovery_retry.sh — rerun the recovery case (natural servo race retry)
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_decision_policy
echo "loadavg: $(cat /proc/loadavg)"
sleep 20   # settle

echo "== battery: recovery (retry) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh recovery > "$E/61_B_recovery_retry.out" 2>&1
grep -E '"outcome"|RECOVERY:|ERR_RECOVERY|run_id' "$E/61_B_recovery_retry.out" | head -8
echo "== decisions tail =="
tail -n 3 /home/ros/.ros/flexcell/decisions.jsonl
