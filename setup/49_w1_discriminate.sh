#!/usr/bin/env bash
# Discriminator: which targets does MoveToPose actually reach?
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py
B=src/flexcell/flexcell_skills/test/ee_probe.py

echo "=== box pose before ==="
timeout 8 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2

for tgt in "0.22 0 0.1375" "0.22 0 0.20" "0.20 0.05 0.20" "0.22 0 0.10"; do
  echo "=== m2p target: $tgt ==="
  timeout 60 python3 $C --pose $tgt 0 0 0 1 --request-id "disc_$(echo $tgt | tr ' .' '__')" 2>&1 | grep -E '"outcome"|position_error_m|detail' | head -3
  echo "  box now: $(timeout 8 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | sed -n 2p)"
done

echo "=== final EE pose ==="
timeout 10 python3 $B world end_effector_link
echo "DISC_DONE"
