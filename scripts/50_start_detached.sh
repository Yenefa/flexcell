#!/usr/bin/env bash
# Start Gazebo + MoveIt detached (setsid+nohup) so they survive the parent shell.
set -u
mkdir -p /tmp/omx
pkill -f 'gz sim|move_group|rviz2|ros2 launch' 2>/dev/null || true
sleep 2

setsid nohup /bin/bash -c '
  source /opt/ros/jazzy/setup.bash
  source /home/ros/agentic_workcell_ws/install/setup.bash
  exec ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py
' > /tmp/omx/gazebo.log 2>&1 < /dev/null &
echo "gazebo launcher pid $!"
sleep 30

setsid nohup /bin/bash -c '
  source /opt/ros/jazzy/setup.bash
  source /home/ros/agentic_workcell_ws/install/setup.bash
  exec ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true
' > /tmp/omx/moveit.log 2>&1 < /dev/null &
echo "moveit launcher pid $!"
echo "DETACHED_STARTED"
