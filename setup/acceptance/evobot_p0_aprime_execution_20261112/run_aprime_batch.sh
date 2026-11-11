#!/usr/bin/env bash
# Execute A-prime's 16 T14 plans through the SAME RunComposite path B used.
#
# FAIRNESS (all six conditions from the audit):
#   1 same 16 T14 ids
#   2 same observation_input.json (build_aprime_plans.py asserts it matches B's)
#   3 same executor path  -> benchmark/tools/run_composite_plan.py, same build_goal
#   4 same frozen evaluate.py v0.5.0  (grading is a separate offline step)
#   5 four numbers reported separately, recovery never folded
#   6 cost column: A-prime 0 model calls
#
# SAFETY: one run at a time under /tmp/evobot_sim.lock; refuses to start if a
# simulator is already running; verifies zero orphans after each run.
set -u

WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
BASE=$WT/setup/acceptance/evobot_p0_aprime_execution_20261112
RUNS=$BASE/runs
LOG=$BASE/logs
mkdir -p "$LOG"

LOCK=/tmp/evobot_sim.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "REFUSING: another lane holds $LOCK"; exit 9
fi
echo "lock acquired"

if pgrep -f '[g]z sim' >/dev/null 2>&1; then
  echo "REFUSING: a gz sim process already exists"; pgrep -af '[g]z sim'; exit 9
fi

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-aprime RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=${EVOBOT_ROS_DOMAIN:-184} LIBGL_ALWAYS_SOFTWARE=1
export PYTHONPATH=$WT/src/flexcell/flexcell_skills:$PYTHONPATH

cleanup() {
  pkill -9 -f '[g]z sim'            2>/dev/null || true
  pkill -9 -f '[r]os2 launch'       2>/dev/null || true
  pkill -9 -f '[c]omposite_server'  2>/dev/null || true
  pkill -9 -f '[p]arameter_bridge'  2>/dev/null || true
  pkill -9 -f '[r]obot_state_publisher' 2>/dev/null || true
  pkill -9 -f '[m]ove_group'        2>/dev/null || true
  pkill -9 -f '[t]ask_fsm_server'   2>/dev/null || true
  sleep 3
}

printf 'task_id\toutcome\terror_code\tdetail\tstages\twall_s\torphans\n' > "$BASE/execution.tsv"

for D in $(ls -d "$RUNS"/HO-* 2>/dev/null | sort); do
  TID=$(basename "$D")
  echo "=== $TID ==="
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
    > "$D/logs_stack.log" 2>&1 &
  STACK=$!
  UP=0
  for i in $(seq 1 90); do
    ros2 action list 2>/dev/null | grep -q run_composite && { UP=1; break; }
    sleep 1
  done
  if [ $UP -ne 1 ]; then
    echo "  STACK_DOWN"
    printf '%s\tHARNESS_ERROR\t-\tstack did not come up\t-\t-\t-\n' "$TID" >> "$BASE/execution.tsv"
    kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true
    cleanup
    continue
  fi
  T0=$(date +%s)
  python3 "$WT/benchmark/tools/run_composite_plan.py" "$D/plan.json" "$D/composite.json" \
    > "$D/logs_exec.log" 2>&1
  RC=$?
  T1=$(date +%s)
  WALL=$((T1-T0))
  kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true
  cleanup
  ORPH=$(pgrep -af '[g]z sim|[p]arameter_bridge|[r]obot_state_publisher|[c]omposite_server' | wc -l)
  OUT=$(python3 -c "import json,sys;d=json.load(open('$D/composite.json'));r=d.get('result',{});print(r.get('outcome'),'|',r.get('error_code'),'|',str(r.get('detail'))[:90].replace(chr(9),' '))" 2>/dev/null || echo 'NO_RESULT')
  echo "  rc=$RC wall=${WALL}s orphans=$ORPH result=$OUT"
  printf '%s\t%s\t%s\n' "$TID" "$WALL" "$ORPH" >> "$BASE/execution_raw.tsv"
  echo "$TID|$OUT|$WALL|$ORPH" >> "$LOG/exec_summary.txt"
done

cleanup
echo AP_PRIME_BATCH_DONE