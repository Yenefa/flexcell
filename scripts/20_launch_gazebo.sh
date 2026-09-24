#!/usr/bin/env bash
set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
set -u
echo "ROS_DISTRO=${ROS_DISTRO}"
echo "DISPLAY=${DISPLAY:-<unset>} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<unset>}"
echo "RMW=${RMW_IMPLEMENTATION:-<default>}"
echo "=== launching Gazebo (open_manipulator_x_gazebo.launch.py) ==="
exec ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py
