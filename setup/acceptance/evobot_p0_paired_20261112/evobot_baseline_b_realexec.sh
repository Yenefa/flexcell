#!/usr/bin/env bash
# Baseline B REAL EXECUTION -- P0 acceptance item 5.
#
# Baseline B v2 planned correctly but its own README says 'Simulation Tested: NO -- no
# Gazebo run'. The mission requires those plans to be handed to the real RunComposite
# executor and graded by the same evaluator A-v2 used. This does that.
#
# The plan is the FROZEN recorded artefact. No model call, no re-plan, no threshold change.
# B never sets agent_claimed_success, so any false_failure it produces is structural.
set -u
OUT=${1:?output dir}
LIMIT=${2:-6}
# Optional explicit task list (space or comma separated). Used to execute the specific
# instances where the A-prime and B plans differ, so the difference is tested on exactly
# the cases that expose it rather than on whatever happens to sort first.
ONLY=${3:-}
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
PLANS=$WT/setup/acceptance/evobot_baseline_b_v2_20261111/plans
mkdir -p "$OUT"

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
source /tmp/t08_push_ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-b RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=${EVOBOT_ROS_DOMAIN:-181} LIBGL_ALWAYS_SOFTWARE=1
export PYTHONPATH=$WT/src/flexcell/flexcell_skills:$PYTHONPATH

# Interface preflight: three wasted simulator starts this session came from guessed
# field names. Fail here instead.
if ! python3 "$WT/benchmark/tools/check_ros_interfaces.py" > "$OUT/interface_check.log" 2>&1; then
  echo 'INTERFACE_CHECK_FAILED'; tail -20 "$OUT/interface_check.log"; exit 1
fi
echo 'interface check: OK'

printf 'task_id\tstages\tcomposite_outcome\tgraded\tpassed\tfalse_success\tfailed_clauses\n' > "$OUT/b_results.tsv"

n=0
if [ -n "$ONLY" ]; then
  CAND=$(echo "$ONLY" | tr "," " " | tr " " "\n" | sed "/^$/d" | sed "s|^|$PLANS/|;s|$|/|")
else
  CAND=$(ls -d "$PLANS"/*/ 2>/dev/null | head -$LIMIT)
fi
for PD in $CAND; do
  TASK=$(basename "$PD")
  n=$((n+1)); echo "=== [$n] $TASK ==="
  SPEC="$WT/benchmark/tasks/train/$TASK.json"
  PLAN="$PD/plan.json"
  [ -f "$PLAN" ] || { echo '  no plan.json'; continue; }
  [ -f "$SPEC" ] || { echo "  no spec: $SPEC"; continue; }
  D="$OUT/$TASK"; mkdir -p "$D"

  pkill -9 -f 'gz sim' 2>/dev/null || true; pkill -9 -f 'ros2 launch' 2>/dev/null || true
  pkill -9 -f composite_server 2>/dev/null || true; pkill -9 -f parameter_bridge 2>/dev/null || true
  pkill -9 -f robot_state_publisher 2>/dev/null || true; sleep 4
  rm -rf "$D/sim"

  python3 -c "import sys;sys.path.insert(0,'/home/ros/flexcell-p14/scripts');import sim_profile;sim_profile.profile('$D/sim','velocity_servo',False,'legacy',0.0,None)"

  setsid ros2 launch flexcell_skills trusted_sim.launch.py world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false > "$D/stack.log" 2>&1 &
  STACK=$!
  UP=0; for i in $(seq 1 90); do ros2 action list 2>/dev/null | grep -q run_composite && { UP=1; break; }; sleep 1; done
  if [ $UP -ne 1 ]; then
    echo '  HARNESS_ERROR: run_composite server never appeared'
    printf '%s\t-\tHARNESS_ERROR\tno\t-\t-\t-\n' "$TASK" >> "$OUT/b_results.tsv"
    kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; sleep 2; continue
  fi

  python3 "$WT/benchmark/tools/run_composite_plan.py" "$PLAN" "$D/composite.json"

  # Ground truth comes from the simulator, never from the plan or the agent.
  python3 - "$SPEC" "$D" <<'PY'
import sys, json
sys.path.insert(0, '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/src/flexcell/flexcell_skills')
spec_path, outdir = sys.argv[1], sys.argv[2]
spec = json.load(open(spec_path))
from flexcell_skills import common
state = {'objects': {}}
for o in spec['objects']:
    pose, err = common.sample_gz_pose(o['name'])
    if pose is not None:
        p = pose[0]; state['objects'][o['name']] = [p[0], p[1], p[2], 0.0]
    else:
        print('  no pose for %s: %s' % (o['name'], err))
json.dump(state, open(outdir + '/gt_after.json', 'w'), indent=2)
print('  captured %d/%d objects' % (len(state['objects']), len(spec['objects'])))
PY

  kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; sleep 2

  python3 - "$SPEC" "$D" "$WT" "$OUT" "$TASK" <<'PY'
import sys, json, subprocess
spec_path, d, wt, out, task = sys.argv[1:6]
try:
    comp = json.load(open(d + '/composite.json'))
except Exception as exc:
    open(out + '/b_results.tsv', 'a').write('%s\t-\tNO_COMPOSITE\tno\t-\t-\t-\n' % task)
    raise SystemExit
stages = len((comp.get('goal') or {}).get('stages') or [])
outcome = (comp.get('result') or {}).get('outcome')
o = subprocess.run([sys.executable, wt + '/benchmark/evaluators/evaluate.py',
                    spec_path, d + '/gt_after.json'], capture_output=True, text=True)
try:
    v = json.loads(o.stdout)
except Exception:
    open(out + '/b_results.tsv', 'a').write('%s\t%s\t%s\tGRADE_ERROR\t-\t-\t-\n'
        % (task, stages, outcome)); raise SystemExit
json.dump(v, open(d + '/verdict.json', 'w'), indent=2)
open(out + '/b_results.tsv', 'a').write('%s\t%s\t%s\tyes\t%s\t%s\t%s\n' % (
    task, stages, outcome, v['passed'], v['false_success'], '|'.join(v['failed_clauses'])))
print('  graded: passed=%s failed=%s' % (v['passed'], v['failed_clauses']))
PY
done

pkill -9 -f 'gz sim' 2>/dev/null || true; pkill -9 -f 'ros2 launch' 2>/dev/null || true
echo; echo '=== BASELINE B REAL EXECUTION ==='
column -t "$OUT/b_results.tsv" 2>/dev/null || cat "$OUT/b_results.tsv"
echo EVOBOT_B_EXEC_DONE