#!/usr/bin/env bash
# Week-1 smoke v2: ensure fresh MoveToPose server, then magnetic carry test.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
E=/mnt/f/flexcell-stage/setup/acceptance/week1
mkdir -p "$E"
cd /home/ros/agentic_workcell_ws
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py

sample_box() {
  timeout 8 gz model -m target_box -p 2>/dev/null | grep -A1 "XYZ" | head -2
}

echo "=== restart move_to_pose server cleanly $(date -Is) ==="
pkill -f move_to_pose_server 2>/dev/null
sleep 2
setsid nohup ros2 launch flexcell_skills move_to_pose.launch.py \
  > "$E/move_to_pose_server.log" 2>&1 < /dev/null &
sleep 7
pgrep -af move_to_pose_server | grep -v grep | head -1

echo "=== sanity: arm reachable via MoveToPose (move to 0.20, 0.05, 0.20) ==="
timeout 60 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --request-id smoke_sanity 2>&1 | grep -E "SENDING|outcome|error_code|position_error_m|wall_seconds|client_error"

echo "=== box pose BEFORE ==="
sample_box

echo "=== ATTACH ==="
timeout 5 gz topic -t /flexcell/target_box/attach -m gz.msgs.Empty -p "" 2>&1
sleep 1

echo "=== move arm to (0.15, -0.15, 0.25) carrying box ==="
timeout 60 python3 "$C" --pose 0.15 -0.15 0.25 0 0 0 1 --request-id smoke_carry 2>&1 | grep -E "SENDING|outcome|error_code|position_error_m|wall_seconds|client_error"

echo "=== box pose AFTER CARRY (expect z ~ 0.25 area, moved with EE) ==="
sample_box

echo "=== DETACH ==="
timeout 5 gz topic -t /flexcell/target_box/attach -m gz.msgs.Empty -p "" 2>&1
sleep 2
echo "=== box pose AFTER DETACH ==="
sample_box
echo "SMOKE2_DONE"
