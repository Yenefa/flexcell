#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
echo "=== how many move_to_pose servers? ==="
pgrep -c -f move_to_pose_server
echo "=== third-party wait_for_service probe ==="
python3 <<'EOF'
import rclpy
from moveit_msgs.srv import GetMotionPlan
rclpy.init()
n = rclpy.create_node('probe_svc')
c = n.create_client(GetMotionPlan, '/plan_kinematic_path')
ok = c.wait_for_service(timeout_sec=5.0)
print('PROBE plan_kinematic_path ready =', ok)
rclpy.shutdown()
EOF
echo "=== restart skill server fresh ==="
pkill -f move_to_pose_server 2>/dev/null
sleep 2
setsid nohup ros2 launch flexcell_skills move_to_pose.launch.py \
  > /mnt/f/flexcell-stage/setup/acceptance/week1/move_to_pose_server.log 2>&1 < /dev/null &
sleep 7
pgrep -c -f move_to_pose_server
echo "=== retry client ==="
timeout 60 python3 src/flexcell/flexcell_skills/test/move_to_pose_client.py --pose 0.20 0.05 0.20 0 0 0 1 --request-id smoke_retry2 2>&1 | grep -E "outcome|error_code|position_error_m|detail|wall_seconds"
echo "PROBE2_DONE"
