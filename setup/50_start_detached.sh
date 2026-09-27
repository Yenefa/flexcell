#!/usr/bin/env bash
# Start Gazebo + MoveIt detached (setsid+nohup) so they survive the parent shell.
set -u
mkdir -p /tmp/omx
# NOTE: robot_state_publisher + parameter_bridge are ros2-launch children whose
# cmdlines do NOT match the launch pattern; a missed kill leaves an orphan RSP
# publishing a STALE latched robot_description (hit 2026-09-26 Week-1).
pkill -f 'gz sim|move_group|rviz2|ros2 launch|robot_state_publisher|parameter_bridge|spawn_entity' 2>/dev/null || true
# skill nodes outlive their launch parent (cmdlines differ) - kill by name too
pkill -f 'move_to_pose_server|observe_server|pick_server|place_server|verify_server|task_fsm_server' 2>/dev/null || true
rm -f /tmp/flexcell_attach_state
sleep 2

setsid nohup /bin/bash -c '
  source /opt/ros/jazzy/setup.bash
  source /home/ros/agentic_workcell_ws/install/setup.bash
  exec ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py world:=/mnt/f/flexcell-stage/worlds/flexcell_world
' > /tmp/omx/gazebo.log 2>&1 < /dev/null &
echo "gazebo launcher pid $!"
sleep 30

setsid nohup /bin/bash -c '
  source /opt/ros/jazzy/setup.bash
  source /home/ros/agentic_workcell_ws/install/setup.bash
  exec ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true
' > /tmp/omx/moveit.log 2>&1 < /dev/null &
echo "moveit launcher pid $!"

# A-level lesson (recurred 2026-09-26): detached moveit launch can die SILENTLY
# (0-byte log). Verify with a bracketed pgrep (no self-match) and retry once.
move_group_ok=0
for i in 1 2 3 4 5 6 7 8 9; do
  sleep 10
  if pgrep -f 'move_grou[p]' > /dev/null; then
    echo "move_group UP after $((i*10))s"
    move_group_ok=1
    break
  fi
  if [ "$i" = "5" ]; then
    echo "move_group missing at 50s - retrying launch once"
    setsid nohup /bin/bash -c '
      source /opt/ros/jazzy/setup.bash
      source /home/ros/agentic_workcell_ws/install/setup.bash
      exec ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true
    ' >> /tmp/omx/moveit.log 2>&1 < /dev/null &
  fi
done
if [ "$move_group_ok" = "1" ]; then
  echo "DETACHED_STARTED"
else
  echo "DETACHED_FAILED: move_group did not come up (see /tmp/omx/moveit.log)"
  exit 1
fi
