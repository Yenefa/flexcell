#!/usr/bin/env bash
# ONE-trial smoke test of the A-prime execution chain, before committing 16 runs.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
BASE=$WT/setup/acceptance/evobot_p0_aprime_execution_20261112
D=$BASE/runs/${1:?task id required}
mkdir -p "$D"

LOCK=/tmp/evobot_sim.lock
exec 9>"$LOCK"
flock -n 9 || { echo "REFUSING: lock held"; exit 9; }
if pgrep -f '[g]z sim' >/dev/null 2>&1; then echo 'REFUSING: gz sim already running'; exit 9; fi
echo "lock acquired for $D"

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-aprime RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=184 LIBGL_ALWAYS_SOFTWARE=1
export PYTHONPATH=$WT/src/flexcell/flexcell_skills:$PYTHONPATH

cleanup() {
  pkill -9 -f '[g]z sim' 2>/dev/null || true
  pkill -9 -f '[r]os2 launch' 2>/dev/null || true
  pkill -9 -f '[c]omposite_server' 2>/dev/null || true
  pkill -9 -f '[p]arameter_bridge' 2>/dev/null || true
  pkill -9 -f '[r]obot_state_publisher' 2>/dev/null || true
  pkill -9 -f '[m]ove_group' 2>/dev/null || true
  pkill -9 -f '[t]ask_fsm_server' 2>/dev/null || true
  sleep 3
}
cleanup
rm -rf "$D/sim"; mkdir -p "$D/sim"
python3 - "$D" <<'PY'
import sys
sys.path.insert(0, '/home/ros/flexcell-p14/scripts')
import sim_profile
sim_profile.profile(sys.argv[1] + '/sim', 'velocity_servo', False, 'legacy', 0.0, None)
print('world:', sys.argv[1] + '/sim/world.sdf')
PY
setsid ros2 launch flexcell_skills trusted_sim.launch.py \
  world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false \
  > "$D/logs_stack.log" 2>&1 &
STACK=$!
UP=0
for i in $(seq 1 90); do
  ros2 action list 2>/dev/null | grep -q run_composite && { UP=1; break; }
  sleep 1
done
echo "stack up=$UP after ${i}s"
if [ $UP -ne 1 ]; then
  echo 'STACK_DOWN'; tail -30 "$D/logs_stack.log"; kill -9 -$STACK 2>/dev/null||true; cleanup; exit 8
fi
T0=$(date +%s)
python3 "$WT/benchmark/tools/run_composite_plan.py" "$D/plan.json" "$D/composite.json" 2>&1 | tee "$D/logs_exec.log"
RC=${PIPESTATUS[0]}
T1=$(date +%s)
echo "exec rc=$RC wall=$((T1-T0))s"
kill -9 -$STACK 2>/dev/null || true
cleanup
echo "orphans: $(pgrep -af '[g]z sim|[p]arameter_bridge|[r]obot_state_publisher|[c]omposite_server' | wc -l)"
echo SMOKE_DONE