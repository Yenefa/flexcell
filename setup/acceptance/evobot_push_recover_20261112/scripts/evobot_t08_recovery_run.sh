#!/usr/bin/env bash
# Closed-loop push recovery: the first REAL test of push_recover.
#
# The same five repeats that produced 2/5 terminal passes with single-shot PushObject.
# Only difference: when a push ends short with contact lost, the policy asks for the
# shortfall and tries again, up to a budget. PushObject itself is untouched; each retry is
# a fresh PushObject goal, which re-approaches the object's CURRENT face automatically.
#
# Prior evidence this must be compared against (same height, same task, same evaluator):
#   single-shot, contact height 0.030 : 0.59 mm, contact never established
#   single-shot, contact height 0.0200: n=5, 2/5 terminal pass, spread 135.2 mm
set -u
OUT=${1:?output dir}
TRIALS=${2:-5}
CONTACT_Z=${3:-0.0200}
ATTEMPTS=${4:-3}
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
TASK=$WT/benchmark/tasks/t08_dev/T08-push-seed2000.json
mkdir -p "$OUT"

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
source /tmp/t08_push_ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-t08 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=${EVOBOT_ROS_DOMAIN:-183} LIBGL_ALWAYS_SOFTWARE=1
export PYTHONPATH=$WT/src/flexcell/flexcell_skills:$PYTHONPATH

if ! python3 "$WT/benchmark/tools/check_ros_interfaces.py" > "$OUT/interface_check.log" 2>&1; then
  echo 'INTERFACE_CHECK_FAILED'; tail -20 "$OUT/interface_check.log"; exit 1
fi
echo 'interface check: OK'

printf 'trial\tattempts\tachieved_mm\trecovery_outcome\ttermminal_passed\tfailed_clauses\n' > "$OUT/recovery.tsv"

for T in $(seq 1 $TRIALS); do
  echo "=== trial $T ==="
  pkill -9 -f 'gz sim' 2>/dev/null || true; pkill -9 -f 'ros2 launch' 2>/dev/null || true
  pkill -9 -f push_server 2>/dev/null || true; pkill -9 -f parameter_bridge 2>/dev/null || true
  pkill -9 -f robot_state_publisher 2>/dev/null || true; sleep 4
  D="$OUT/t$T"; mkdir -p "$D"; rm -rf "$D/sim"

  python3 -c "import sys;sys.path.insert(0,'/home/ros/flexcell-p14/scripts');import sim_profile;sim_profile.profile('$D/sim','velocity_servo',False,'legacy',0.0,None)"

  setsid ros2 launch flexcell_skills trusted_sim.launch.py world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false > "$D/stack.log" 2>&1 &
  STACK=$!
  UP=0; for i in $(seq 1 90); do ros2 action list 2>/dev/null | grep -q push_object && { UP=1; break; }; sleep 1; done
  if [ $UP -ne 1 ]; then
    echo '  HARNESS_ERROR: push_object server never appeared'
    printf '%s\tHARNESS_ERROR\n' "$T" >> "$OUT/recovery.tsv"
    kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; sleep 2; continue
  fi

  python3 "$WT/src/flexcell/flexcell_skills/run_push_recovery.py" \
      "$TASK" "$D" "$CONTACT_Z" "$ATTEMPTS"

  # Ground truth from the simulator, then the frozen evaluator. Never from the policy.
  python3 - "$TASK" "$D" <<'PYEOF'
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
PYEOF

  kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; sleep 2

  python3 - "$TASK" "$D" "$WT" "$OUT" "$T" <<'PYEOF'
import sys, json, subprocess
task_path, d, wt, out, trial = sys.argv[1:6]
try:
    rec = json.load(open(d + '/recovery.json'))
except Exception:
    open(out + '/recovery.tsv', 'a').write('%s\tNO_RECOVERY\n' % trial); raise SystemExit
o = subprocess.run([sys.executable, wt + '/benchmark/evaluators/evaluate.py',
                    task_path, d + '/gt_after.json'], capture_output=True, text=True)
try:
    v = json.loads(o.stdout)
except Exception:
    open(out + '/recovery.tsv', 'a').write('%s\tGRADE_ERROR\n' % trial); raise SystemExit
json.dump(v, open(d + '/verdict.json', 'w'), indent=2)
verdict = rec['verdict']
open(out + '/recovery.tsv', 'a').write('%s\t%d\t%.2f\t%s\t%s\t%s\n' % (
    trial, verdict['attempts'], verdict['achieved_m'] * 1000, verdict['outcome'],
    v['passed'], '|'.join(v['failed_clauses'])))
print('  graded: terminal_passed=%s failed=%s' % (v['passed'], v['failed_clauses']))
PYEOF
done

pkill -9 -f 'gz sim' 2>/dev/null || true; pkill -9 -f 'ros2 launch' 2>/dev/null || true
echo
echo '=== CLOSED-LOOP RECOVERY RESULTS ==='
column -t "$OUT/recovery.tsv" 2>/dev/null || cat "$OUT/recovery.tsv"
echo EVOBOT_RECOVERY_DONE