#!/usr/bin/env bash
# Minimal attach-loop isolation: toggle -> move -> did the box follow?
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py

echo "=== box before ==="
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2

echo "=== manual toggle #1 (expect ATTACH) ==="
timeout 5 gz topic -t /flexcell/target_box/attach -m gz.msgs.Empty -p ""
echo "publish rc=$?"
sleep 1

echo "=== move arm up to (0.15, -0.1, 0.28) ==="
timeout 60 python3 $C --pose 0.15 -0.1 0.28 0 0 0 1 --request-id iso1 2>&1 | grep -E '"outcome"|position_error_m' | head -2

echo "=== box after (attached => z ~ 0.12; detached => z ~ 0.0175) ==="
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2

echo "=== manual toggle #2 (expect DETACH) ==="
timeout 5 gz topic -t /flexcell/target_box/attach -m gz.msgs.Empty -p ""
sleep 2
echo "=== box after detach ==="
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2
echo "ISO_DONE"
