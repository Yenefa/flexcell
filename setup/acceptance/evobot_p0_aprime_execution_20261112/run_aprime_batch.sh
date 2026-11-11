#!/usr/bin/env bash
# EXECUTE A-prime's 16 T14 plans through the SAME RunComposite path B used.
#
# FAIRNESS (all six conditions):
#   1 same 16 T14 ids
#   2 same observation_input.json (asserted byte-identical to B's by build_aprime_plans.py)
#   3 same executor: benchmark/tools/run_composite_plan.py -> RunComposite 'run_composite'
#     (served by task_fsm_server, task_fsm_server.py:288-293)
#   4 same frozen evaluate.py v0.5.0 (grading is the separate offline step)
#   5 four numbers per arm, recovery never folded
#   6 cost: A-prime 0 model calls
#
# SAFETY: one run at a time under /tmp/evobot_sim.lock; refuses to start if a sim
# is already running; zero orphans verified after every run; stack is killed only
# AFTER the result and ground truth are captured.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
BASE=$WT/setup/acceptance/evobot_p0_aprime_execution_20261112
RUNS=$BASE/runs
RES=$BASE/results
mkdir -p "$RES"

LOCK=/tmp/evobot_sim.lock
exec 9>"$LOCK"
if ! flock -n 9; then echo 'REFUSING: another lane holds the sim lock'; exit 9; fi
if pgrep -f '[g]z sim' >/dev/null 2>&1; then echo 'REFUSING: gz sim already running'; exit 9; fi
echo 'lock acquired; no simulator running'

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-aprime RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=186 LIBGL_ALWAYS_SOFTWARE=1
# DO NOT prepend the worktree's flexcell_skills. It shadows the installed stack with
# a version whose task_fsm_server.py:44 imports PushObject, an action added to the
# worktree for T08 that was never built into flexcell-p14-ws. Result: task_fsm_server
# dies with ImportError, /run_composite never appears, and every trial reports
# STACK_DOWN. Measured, not guessed.
#
# Using the INSTALLED stack is also the fairness-correct choice: the archived B runs
# used /home/ros/flexcell-p14 (see evobot_run_b.sh), so A-prime must use the same one.
# Fairness condition 3 is "same executor path", and the executor is the installed node.
export FLEXCELL_REPO=/home/ros/flexcell-p14
export FLEXCELL_WS=/home/ros/flexcell-p14-ws
export FLEXCELL_INSTALL=/home/ros/flexcell-p14-ws/install

kill_stack() {
  [ -n "${STACK:-}" ] && { kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; }
  pkill -9 -f '[g]z sim' 2>/dev/null || true
  pkill -9 -f '[r]os2 launch' 2>/dev/null || true
  pkill -9 -f '[t]ask_fsm_server' 2>/dev/null || true
  pkill -9 -f '[p]arameter_bridge' 2>/dev/null || true
  pkill -9 -f '[r]obot_state_publisher' 2>/dev/null || true
  pkill -9 -f '[m]ove_group' 2>/dev/null || true
  pkill -9 -f '[m]ove_to_pose_server' 2>/dev/null || true
  pkill -9 -f '[o]bserve_server' 2>/dev/null || true
  pkill -9 -f '[p]ick_server' 2>/dev/null || true
  pkill -9 -f '[p]lace_server' 2>/dev/null || true
  pkill -9 -f '[v]erify_server' 2>/dev/null || true
  pkill -9 -f '[c]arry_server' 2>/dev/null || true
  sleep 4
}

printf 'task_id\tstack_up\toutcome\terror_code\tcompleted_stages\twall_s\torphans\tgt_captured\n' > "$BASE/execution.tsv"

for D in $(ls -d "$RUNS"/HO-* | sort); do
  TID=$(basename "$D")
  echo "=== $TID ==="
  kill_stack
  STACK=''
  rm -rf "$D/sim"; mkdir -p "$D/sim"
  python3 - "$D" <<'PY' 2>/dev/null || true
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
  for i in $(seq 1 150); do
    if ros2 action list 2>/dev/null | grep -q '/run_composite'; then UP=1; break; fi
    sleep 1
  done
  if [ $UP -ne 1 ]; then
    echo '  STACK_DOWN'
    # Record WHY, so a future reader is not left guessing as I was.
    grep -iE 'Traceback|ImportError|ModuleNotFound|died|ERROR' "$D/logs_stack.log" | head -6 >> "$D/logs_stack_diag.txt" 2>/dev/null || true
    printf '%s\t0\tHARNESS_ERROR\t-\t-\t-\t-\t-\n' "$TID" >> "$BASE/execution.tsv"
    kill_stack; continue
  fi
  T0=$(date +%s)
  python3 "$WT/benchmark/tools/run_composite_plan.py" "$D/plan.json" "$D/composite.json" \
    > "$D/logs_exec.log" 2>&1
  T1=$(date +%s)
  WALL=$((T1-T0))
  # capture ground truth BEFORE killing the stack
  python3 "$WT/benchmark/evaluators/capture_ground_truth.py" "$D/ground_truth.json" \
    target_box_a target_box_b > "$D/logs_gt.log" 2>&1
  GTOK=0; [ -s "$D/ground_truth.json" ] && GTOK=1
  STAGEIDS=$(python3 -c "import json;d=json.load(open('$D/composite.json'));r=d.get('result',{});print(','.join(r.get('completed_stage_ids') or []) or '-')" 2>/dev/null || echo 'NO_RESULT')
  OUTCOME=$(python3 -c "import json;d=json.load(open('$D/composite.json'));r=d.get('result',{});print(r.get('outcome'),r.get('error_code'))" 2>/dev/null | tr ' ' '\t' || echo 'NA\tNA')
  kill_stack
  ORPH=$(pgrep -f '[g]z sim' | wc -l)
  echo "  up=1 wall=${WALL}s gt=$GTOK orphans=$ORPH outcome=$OUTCOME stages=$STAGEIDS"
  printf '%s\t1\t%s\t%s\t%s\t%s\t%s\n' "$TID" "$OUTCOME" "$STAGEIDS" "$WALL" "$ORPH" "$GTOK" >> "$BASE/execution.tsv"
done

kill_stack
echo AP_PRIME_BATCH_DONE
