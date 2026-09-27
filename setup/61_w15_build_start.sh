#!/usr/bin/env bash
# Week-1.5 build + legacy cleanup + first managed start
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

echo "=== sync + rebuild (interfaces + skills) ==="
cp -r /mnt/f/flexcell-stage/agentic_workcell_ws/src/flexcell/. src/flexcell/
colcon build --symlink-install --packages-select flexcell_interfaces flexcell_skills 2>&1 | tail -2

echo "=== one-time legacy cleanup (pre-lifecycle processes) ==="
pkill -f 'gz sim|move_group|rviz2|ros2 launch|robot_state_publisher|parameter_bridge|spawn_entity'
pkill -f 'move_to_pose_server|observe_server|pick_server|place_server|verify_server|task_fsm_server|carry_server'
sleep 4
echo "residue: $(pgrep -c -f 'move_grou[p]|gz si[m]|flexcell_skills')"

echo "=== flexcell start (managed) ==="
tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > /tmp/flexcell_cli
bash /tmp/flexcell_cli start 2>&1 | tail -30
echo "START_RC=$?"
echo "BUILDANDSTART_DONE"
