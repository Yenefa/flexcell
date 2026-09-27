#!/usr/bin/env bash
set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
set -u
echo "=== launching MoveIt 2 (use_sim:=true) ==="
exec ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true
