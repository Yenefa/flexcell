#!/usr/bin/env bash
# Week-1 solo test: fleet up -> observe -> full task (happy path).
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
E=/mnt/f/flexcell-stage/setup/acceptance/week1

setsid nohup ros2 launch flexcell_skills move_to_pose.launch.py \
  > "$E/move_to_pose_server.log" 2>&1 < /dev/null &
setsid nohup ros2 launch flexcell_skills week1.launch.py \
  > "$E/week1_servers.log" 2>&1 < /dev/null &
sleep 14
echo "fleet: m2p=$(pgrep -c -f 'move_to_pose_se[r]ver') obs=$(pgrep -c -f 'observe_se[r]ver') pick=$(pgrep -c -f 'pick_se[r]ver') place=$(pgrep -c -f 'place_se[r]ver') verify=$(pgrep -c -f 'verify_se[r]ver') fsm=$(pgrep -c -f 'task_fsm_se[r]ver')"

echo "=== SOLO observe ==="
timeout 30 python3 test/w1_client.py --action observe 2>&1 | tail -16

echo "=== SOLO task happy (place at 0.12,-0.15,0.0175) ==="
timeout 170 python3 test/w1_client.py --action task --object target_box --pose 0.12 -0.15 0.0175 2>&1 | tail -22
echo "SOLO_DONE"
