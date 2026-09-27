#!/usr/bin/env bash
cd /home/ros/agentic_workcell_ws
git config user.name "Yenefa"
git config user.email "sca331613@gmail.com"
git commit -m "Week 1 (local): deterministic skills observe/pick/place/verify + task FSM + carry servo

- flexcell_interfaces: WorldState/WorldObject msgs + Observe/PickObject/
  PlaceObject/VerifyObject/RunPickPlace actions
- flexcell_skills: observe/pick/place/verify/task_fsm/carry servers +
  common.py helpers + week1.yaml + week1.launch.py
- carry = teleport servo via /world/empty/set_pose @10Hz (DetachableJoint
  abandoned: subscriber loss after first cycle / silent joint failures /
  one-shot publish delivery races - see 踩坑日记 2026-09-26 A-level entry)
- acceptance: full chain OBSERVE->PICK->PLACE->VERIFY SUCCEEDED at 4.9-6.5mm
  ground-truth error; negative paths typed; Day-2 battery 10/10 regression-free
- evidence: F:/flexcell-stage/setup/acceptance/week1/ (battery 47 + archive 58)
NOTE: local commit only - push requires explicit authorization." | tail -2
echo "=== log ==="
git log --oneline -3
echo "=== dedupe carry server ==="
pkill -f 'carry_se[r]ver'
sleep 2
source /opt/ros/jazzy/setup.bash
source install/setup.bash
setsid nohup ros2 run flexcell_skills carry_server --ros-args --params-file /home/ros/agentic_workcell_ws/install/flexcell_skills/share/flexcell_skills/config/week1.yaml -p use_sim_time:=true > /mnt/f/flexcell-stage/setup/acceptance/week1/carry_server.log 2>&1 < /dev/null &
sleep 4
echo "carry count: $(pgrep -c -f 'carry_se[r]ver')"
echo "=== box pose ==="
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2
echo "WRAPUP2_DONE"
