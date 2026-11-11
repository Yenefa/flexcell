#!/usr/bin/env bash
# DETERMINISM CONTROL: same five pushes, but with real_time_factor=0 in the generated
# world copy so physics is not paced by wall-clock scheduling.
#
# This is the experiment the variance investigation asks for. Five byte-identical
# worlds produced displacements from 4.2 to 137.8 mm. Two hypotheses explain that:
#   H1 real-time pacing couples physics steps to ROS command arrival, so the contact
#      instant differs each run;
#   H2 the control target (end_effector_link, no collision geometry) and the real
#      contact bodies (two gripper fingers) diverge with arm pose, so tiny pose
#      differences flip between 'caught' and 'slipped'.
# Removing wall-clock pacing tests H1. If the spread collapses, H1 is supported. If it
# persists, H1 alone is insufficient and H2 (or something else) remains.
#
# ONLY the generated world copy is patched. sim_profile.py, the skill, the evaluator,
# TaskSpec and every frozen threshold are untouched. Dev instance only, never held-out.
set -u
OUT=${1:?output dir}; N=${2:-5}
TASK=${3:-/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/benchmark/tasks/t08_dev/T08-push-seed2000.json}
mkdir -p "$OUT"
set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
source /tmp/t08_push_ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-t08 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=${EVOBOT_ROS_DOMAIN:-180} LIBGL_ALWAYS_SOFTWARE=1
echo 'trial  displacement_mm  increments  contact_lost_at  direction_cos' > "$OUT/repeats.tsv"
OBJ=$(python3 -c "import json;print(json.load(open('$TASK'))['objects'][0]['name'])")
for T in $(seq 1 $N); do
  pkill -9 -f 'gz sim' 2>/dev/null || true; pkill -9 -f 'ros2 launch' 2>/dev/null || true
  pkill -9 -f push_server 2>/dev/null || true; pkill -9 -f parameter_bridge 2>/dev/null || true
  pkill -9 -f robot_state_publisher 2>/dev/null || true; sleep 4
  D="$OUT/t$T"; mkdir -p "$D"; rm -rf "$D/sim"
  python3 - "$D" <<PY
import sys
sys.path.insert(0, '/home/ros/flexcell-p14/scripts')
import sim_profile
sim_profile.profile(sys.argv[1] + '/sim', 'velocity_servo', False, 'legacy', 0.0, None)
PY
  # Patch ONLY the generated copy, and fail loudly if the anchor is not exactly there.
  python3 - "$D/sim/world.sdf" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
old = '<real_time_factor>1</real_time_factor>'
assert s.count(old) == 1, 'expected exactly one real_time_factor=1, got %d' % s.count(old)
open(p, 'w', encoding='utf-8').write(s.replace(old, '<real_time_factor>0</real_time_factor>'))
print('  patched real_time_factor 1 -> 0 in generated world copy')
PY
  if grep -q '<real_time_factor>1<' "$D/sim/world.sdf"; then
    echo '  HARNESS_ERROR: patch did not take'; printf '%s\tHARNESS_ERROR\n' "$T" >> "$OUT/repeats.tsv"; continue
  fi
  setsid ros2 launch flexcell_skills trusted_sim.launch.py world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false > "$D/stack.log" 2>&1 &
  STACK=$!
  UP=0; for i in $(seq 1 90); do ros2 action list 2>/dev/null | grep -q push_object && { UP=1; break; }; sleep 1; done
  if [ $UP -ne 1 ]; then
    echo '  HARNESS_ERROR: action server never appeared'
    printf '%s\tHARNESS_ERROR\n' "$T" >> "$OUT/repeats.tsv"
    kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; sleep 2; continue
  fi
  python3 - "$OBJ" "$D" <<'PY'
import sys, json
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from flexcell_interfaces.action import PushObject
obj, outdir = sys.argv[1], sys.argv[2]
rclpy.init(); node = Node('det')
c = ActionClient(node, PushObject, 'push_object'); res = {'error': 'no server'}
if c.wait_for_server(timeout_sec=30.0):
    g = PushObject.Goal(); g.request_id = 'det'
    g.object_name = obj
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = 0.09; g.contact_height_m = 0.0200; g.overdrive_m = float('nan')
    f = c.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    gh = f.result()
    if gh and gh.accepted:
        rf = gh.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
        r = rf.result().result
        res = {n: getattr(r, n) for n in PushObject.Result.get_fields_and_field_types()
               if not hasattr(getattr(r, n), '__slots__')}
json.dump(res, open(outdir + '/push.json', 'w'), indent=2, default=str)
node.destroy_node(); rclpy.shutdown()
PY
  kill -9 -$STACK 2>/dev/null || true; kill -9 $STACK 2>/dev/null || true; sleep 2
  python3 - "$D" "$OUT" "$T" <<'PY'
import json, sys
d_out, out, t = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.load(open(d_out + '/push.json'))
    row = '%s\t%.2f\t%s\t%s\t%.4f\n' % (t, float(d.get('displacement_m') or 0)*1000,
        d.get('increments_executed'), d.get('contact_lost_at_increment'), float(d.get('direction_cos') or 0))
except Exception as e:
    row = '%s\tERROR\t%s\n' % (t, e)
open(out + '/repeats.tsv', 'a').write(row)
PY
done
pkill -9 -f 'gz sim' 2>/dev/null || true; pkill -9 -f 'ros2 launch' 2>/dev/null || true
echo; echo '=== FIXED-STEP REPEATS ==='; cat "$OUT/repeats.tsv"
python3 - "$OUT" <<'PY'
import sys, statistics
vals = []
for line in open(sys.argv[1] + '/repeats.tsv').read().splitlines()[1:]:
    p = line.split('\t')
    if len(p) > 1 and p[1] not in ('HARNESS_ERROR', 'ERROR'):
        try: vals.append(float(p[1]))
        except ValueError: pass
if vals:
    print('n=%d  min=%.1f  median=%.1f  max=%.1f  spread=%.1f mm' % (len(vals), min(vals), statistics.median(vals), max(vals), max(vals)-min(vals)))
    print('above 30mm gate: %d/%d' % (sum(1 for v in vals if v >= 30), len(vals)))
PY
echo T08_FIXEDSTEP_DONE
