#!/usr/bin/env bash
# G1 / G3 gripper-aperture calibration: one Gazebo run per mode.
#
# Same world, same instance poses, same stack as the push trials, so the
# aperture measurement is taken on the machine the gate actually judges.
set -u

OUT="$1"; MODE="$2"; TASK="$3"
if [ -z "$OUT" ] || [ -z "$MODE" ] || [ -z "$TASK" ]; then
  echo "usage: run_gripper_calibration.sh <outdir> <G1|G3> <task.json>"; exit 2
fi

WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
IP=$WT/setup/acceptance/evobot_t08_instance_pose_20261112
OLD=$WT/setup/acceptance/evobot_t08_evidence_loop_20261112/scripts
SCRIPTS=$IP/runs/scripts
DOMAIN=183

mkdir -p "$OUT"
exec 9>/tmp/evobot_sim.lock
if ! flock -w 60 9; then echo "REFUSED: sim lock held"; exit 9; fi
if pgrep -f "[g]z sim" > /dev/null 2>&1; then
  echo "REFUSED: gz sim already running"; pgrep -af "[g]z sim" | head -3; exit 9
fi

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash 2>/dev/null
source /home/ros/flexcell-p14-ws/install/setup.bash 2>/dev/null
source /tmp/t08_push_ws/install/setup.bash 2>/dev/null
export PYTHONPATH="$WT/src/flexcell/flexcell_skills:$PYTHONPATH"
set -u
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID="$DOMAIN"
export GZ_PARTITION=evobot-t08cal LIBGL_ALWAYS_SOFTWARE=1

D="$OUT"
rm -rf "$D/sim"; mkdir -p "$D/logs"

python3 - "$D" <<'PY' > "$D/logs/sim_profile.log" 2>&1
import sys
sys.path.insert(0, "/home/ros/flexcell-p14/scripts")
import sim_profile
params, world = sim_profile.profile(sys.argv[1] + "/sim", "velocity_servo", False, "legacy", 0.0, None)
print("params", params); print("world", world)
PY
WORLD="$D/sim/world.sdf"; PARAMS="$D/sim/params.yaml"
[ -f "$WORLD" ] || { echo "NO_WORLD"; exit 4; }

python3 "$OLD/inject_contact_evidence.py" "$WORLD" > "$D/logs/inject.log" 2>&1 || { echo "INJECT_FAILED"; exit 4; }
python3 "$IP/inject_instance_poses.py" "$WORLD" "$TASK" > "$D/logs/inject_poses.log" 2>&1 || { echo "POSE_INJECT_FAILED"; exit 4; }

export FLEXCELL_CONTACT_STEP_LOG="$D/logs/contact_steps.jsonl"
export FLEXCELL_PHYSICS_STEP_LOG="$D/logs/physics_steps.jsonl"
rm -f "$FLEXCELL_CONTACT_STEP_LOG" "$FLEXCELL_PHYSICS_STEP_LOG"

setsid ros2 launch flexcell_skills trusted_sim.launch.py     world:="$WORLD" params_file:="$PARAMS" camera:=false > "$D/logs/stack.log" 2>&1 &
STACK=$!
UP=0
for i in $(seq 1 120); do
  if ros2 action list 2>/dev/null | grep -q move_to_pose; then UP=1; echo "  move_to_pose up after ${i}s"; break; fi
  if ! kill -0 "$STACK" 2>/dev/null; then echo "  stack died"; break; fi
  sleep 1
done
if [ "$UP" -ne 1 ]; then echo "CALIB_STACK_UNAVAILABLE"; kill -9 -"$STACK" 2>/dev/null; exit 5; fi
sleep 3

python3 "$SCRIPTS/gripper_calibration.py" "$MODE" "$D" "$TASK" > "$D/logs/calibration_driver.log" 2>&1
RC=$?
tail -25 "$D/logs/calibration_driver.log"

kill -9 -"$STACK" 2>/dev/null; kill -9 "$STACK" 2>/dev/null
for pat in "[g]z sim" "[r]os2 launch" "[p]arameter_bridge" "[r]obot_state_publisher" "[m]ove_group" "[p]ush_server" "[c]arry_server" "[p]ick_server" "[p]lace_server" "[o]bserve_server" "[v]erify_server" "[t]ask_fsm_server" "[m]ove_to_pose_server" "[m]tc_planner" "[r]viz2"; do
  pkill -9 -f "$pat" 2>/dev/null || true
done
sleep 2
echo "orphans=$(pgrep -cf '[g]z sim|[p]arameter_bridge|[r]obot_state_publisher|[p]ush_server' || echo 0)"
echo "CALIB_DONE rc=$RC mode=$MODE"
