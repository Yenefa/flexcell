#!/usr/bin/env bash
# Validate: persistent ros_gz_bridge (ROS->GZ) + ros2 topic pub --once for the toggle.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py

echo "=== start persistent bridge (ROS -> GZ) ==="
setsid nohup ros2 run ros_gz_bridge parameter_bridge "/flexcell/target_box/attach@std_msgs/msg/Empty]gz.msgs.Empty" \
  > /tmp/omx/attach_bridge.log 2>&1 < /dev/null &
sleep 5
timeout 6 ros2 topic info /flexcell/target_box/attach -v 2>/dev/null | grep -E "Type|Publishers|Subscribers|gz" | head -6

echo "=== box before ==="
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2

echo "=== ROS publish ONCE (expect ATTACH via bridge) ==="
timeout 10 ros2 topic pub --once -w 1 /flexcell/target_box/attach std_msgs/msg/Empty "{}" 2>&1 | head -2
sleep 1

echo "=== move arm (0.15,-0.1,0.28 -> 0.20,0.05,0.24) ==="
timeout 60 python3 $C --pose 0.20 0.05 0.24 0 0 0 1 --request-id iso2a 2>&1 | grep -E '"outcome"|position_error_m' | head -2

echo "=== box after (z~0.08 = attached; z~0.0175 = not) ==="
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2

echo "=== ROS publish ONCE again (expect DETACH) ==="
timeout 10 ros2 topic pub --once -w 1 /flexcell/target_box/attach std_msgs/msg/Empty "{}" 2>&1 | head -1
sleep 2
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2
echo "ISO2_DONE"
