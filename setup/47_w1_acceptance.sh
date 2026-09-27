#!/usr/bin/env bash
# Week-1 acceptance battery (self-contained clean run):
#   restart stack -> launch all skill servers -> run cases -> leave a clean stack.
# Run inside WSL as user ros.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
CL=src/flexcell/flexcell_skills/test/w1_client.py
E=/mnt/f/flexcell-stage/setup/acceptance/week1
mkdir -p "$E"

echo "########## 0) clean restart ##########"
bash /tmp/50start.sh 2>&1 | tail -2
pkill -f 'move_to_pose_server|observe_server|pick_server|place_server|verify_server|task_fsm_server' 2>/dev/null
sleep 2
setsid nohup ros2 launch flexcell_skills move_to_pose.launch.py > "$E/move_to_pose_server.log" 2>&1 < /dev/null &
setsid nohup ros2 launch flexcell_skills week1.launch.py > "$E/week1_servers.log" 2>&1 < /dev/null &
sleep 14
echo "servers: m2p=$(pgrep -c -f 'move_to_pose_se[r]ver') w1=$(pgrep -c -f 'observe_ser[v]er')/$(pgrep -c -f 'pick_se[r]ver')/$(pgrep -c -f 'place_se[r]ver')/$(pgrep -c -f 'verify_se[r]ver')/$(pgrep -c -f 'task_fsm_se[r]ver')"
pgrep -f 'move_grou[p]' > /dev/null && echo "move_group UP" || echo "move_group DOWN"

case_run() {  # case_run <name> <expect> -- client args...
  local name="$1"; local expect="$2"; shift 2
  {
    echo "=== ${name} | $(date -Is) | EXPECT: ${expect} ==="
    timeout 170 python3 "$CL" "$@"
    echo "RC=$?"
  } 2>&1 | tee "$E/${name}.out"
  echo
}

case_run w1_1_observe "SUCCEEDED revision>=1 box@(0.22,0,0.0175)" --action observe
case_run w1_2_task_happy "SUCCEEDED trace=OBSERVE,PICK,PLACE,VERIFY object_at_place" --action task --object target_box --pose 0.12 -0.15 0.0175
case_run w1_3_verify_post "VERIFIED at (0.12,-0.15,0.0175)" --action verify --object target_box --pose 0.12 -0.15 0.0175
case_run w1_4_pick_unknown "OBJECT_UNKNOWN" --action pick --object no_such_box
case_run w1_5_place_not_carried "NOT_CARRIED" --action place --object target_box --pose 0.20 0.0 0.0175

echo "########## w1_6 busy: two concurrent tasks ##########"
{
  echo "=== w1_6_busy | $(date -Is) | EXPECT: first SUCCEEDED, second RESOURCE_BUSY ==="
  timeout 170 python3 "$CL" --action task --object target_box --pose 0.25 0.05 0.0175 > /tmp/w1_6a.out 2>&1 &
  P1=$!
  sleep 2.5
  timeout 60 python3 "$CL" --action task --object target_box --pose 0.25 0.05 0.0175 > /tmp/w1_6b.out 2>&1
  echo "second-task RC=$?"
  grep -E "outcome|error_code|detail" /tmp/w1_6b.out | head -4
  echo "--- first task result ---"
  wait $P1
  echo "first-task RC=$?"
  grep -E "\"outcome\"|object_at_place|final_position_error" /tmp/w1_6a.out | head -4
} 2>&1 | tee "$E/w1_6_busy.out"
echo

echo "########## w1_7 unreachable place (box currently at 0.25,0.05) ##########"
case_run w1_7_place_unreachable "SKILL_FAILED with IK_UNREACHABLE from PLACE" --action task --object target_box --pose 0.42 0.0 0.0175

echo "########## 8) leave a clean stack for inspection ##########"
bash /tmp/50start.sh 2>&1 | tail -2
pkill -f 'move_to_pose_server|observe_server|pick_server|place_server|verify_server|task_fsm_server' 2>/dev/null
sleep 2
setsid nohup ros2 launch flexcell_skills move_to_pose.launch.py > "$E/move_to_pose_server.log" 2>&1 < /dev/null &
setsid nohup ros2 launch flexcell_skills week1.launch.py > "$E/week1_servers.log" 2>&1 < /dev/null &
sleep 12
pgrep -f 'move_grou[p]' > /dev/null && echo "final: move_group UP" || echo "final: move_group DOWN"
echo "final server counts (expect 1 each): m2p=$(pgrep -c -f 'move_to_pose_se[r]ver') obs=$(pgrep -c -f 'observe_se[r]ver') pick=$(pgrep -c -f 'pick_se[r]ver') place=$(pgrep -c -f 'place_se[r]ver') verify=$(pgrep -c -f 'verify_se[r]ver') fsm=$(pgrep -c -f 'task_fsm_se[r]ver')"
echo "BATTERY_DONE"
