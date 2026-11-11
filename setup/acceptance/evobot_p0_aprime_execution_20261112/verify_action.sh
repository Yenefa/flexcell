#!/usr/bin/env bash
# Verify the run_composite action server actually appears on a live stack.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
D=$WT/setup/acceptance/evobot_p0_aprime_execution_20261112/runs/HO-0dcde4dc0f5a
exec 9>/tmp/evobot_sim.lock
flock -n 9 || { echo REFUSING_LOCK; exit 9; }
set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-aprime RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=185 LIBGL_ALWAYS_SOFTWARE=1
cleanup() {
  pkill -9 -f '[g]z sim' 2>/dev/null||true; pkill -9 -f '[r]os2 launch' 2>/dev/null||true
  pkill -9 -f '[t]ask_fsm_server' 2>/dev/null||true; pkill -9 -f '[p]arameter_bridge' 2>/dev/null||true
  pkill -9 -f '[r]obot_state_publisher' 2>/dev/null||true; pkill -9 -f '[m]ove_group' 2>/dev/null||true
  pkill -9 -f '[m]ove_to_pose_server' 2>/dev/null||true; pkill -9 -f '[o]bserve_server' 2>/dev/null||true
  pkill -9 -f '[p]ick_server' 2>/dev/null||true; pkill -9 -f '[p]lace_server' 2>/dev/null||true
  pkill -9 -f '[v]erify_server' 2>/dev/null||true; pkill -9 -f '[c]arry_server' 2>/dev/null||true
  sleep 3
}
cleanup
rm -rf "$D/sim"; mkdir -p "$D/sim"
python3 - "$D" <<'PY'
import sys
sys.path.insert(0, '/home/ros/flexcell-p14/scripts')
import sim_profile
sim_profile.profile(sys.argv[1] + '/sim', 'velocity_servo', False, 'legacy', 0.0, None)
PY
setsid ros2 launch flexcell_skills trusted_sim.launch.py \
  world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false \
  > /tmp/verify_stack.log 2>&1 &
STACK=$!
echo 'waiting up to 90s for run_composite...'
FOUND=0
for i in $(seq 1 90); do
  if ros2 action list 2>/dev/null | grep -q run_composite; then FOUND=1; echo "FOUND run_composite after ${i}s"; break; fi
  sleep 1
done
echo '=== full action list ==='
ros2 action list 2>/dev/null | sort
echo "=== run_composite present: $FOUND ==="
echo '=== node list (grep fsm) ==='
ros2 node list 2>/dev/null | grep -i fsm
kill -9 -$STACK 2>/dev/null||true
cleanup
echo "orphans: $(pgrep -f 'gz sim' | wc -l)"
echo VERIFY_DONE
