#!/usr/bin/env bash
# Contact-height sweep: the cheapest falsifiable hypothesis for T08 saturation.
#
# The diagnosis says the push saturates because contact is lost after ~20 mm and
# the skill then gives up. Before building retry logic, test whether the CONTACT
# POINT ITSELF is the problem: the block is 35 mm tall, centre at z=0.0175, and the
# current height of 0.030 puts the fingertip 12.5 mm ABOVE the centre -- likely on
# the top edge rather than the face, where it slips off.
#
# Each height is one real push in a fresh world. Same task, same direction, same
# distance. Only contact_height_m changes.
set -u
S=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
OUT=${1:-/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence/t08_height_sweep_20261112}
TASK=$WT/benchmark/tasks/t08_dev/T08-push-seed2000.json
mkdir -p "$OUT"

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
source /tmp/t08_push_ws/install/setup.bash
set -u

OBJ=$(python3 -c "import json;print(json.load(open('$TASK'))['objects'][0]['name'])")
echo "object=$OBJ  task=$TASK"
echo 'height_m  displacement_mm  outcome  contact_made  contact_lost' > "$OUT/sweep.tsv"

for H in 0.0175 0.0200 0.0225 0.0250 0.0300; do
  echo "=== contact_height=$H ==="
  pkill -9 -f 'gz sim' 2>/dev/null || true
  pkill -9 -f 'ros2 launch' 2>/dev/null || true
  pkill -9 -f 'push_server' 2>/dev/null || true
  pkill -9 -f 'parameter_bridge' 2>/dev/null || true
  pkill -9 -f 'robot_state_publisher' 2>/dev/null || true
  sleep 4
  HOUT="$OUT/h$H"
  mkdir -p "$HOUT"
  rm -rf "$HOUT/sim"
  python3 - "$HOUT" <<PY
import sys
sys.path.insert(0, '/home/ros/flexcell-p14/scripts')
import sim_profile
params, world = sim_profile.profile(sys.argv[1] + '/sim', 'velocity_servo', False, 'legacy', 0.0, None)
print(params); print(world)
PY
  PARAMS=$HOUT/sim/params.yaml; WORLD=$HOUT/sim/world.sdf
  setsid ros2 launch flexcell_skills trusted_sim.launch.py world:=$WORLD params_file:=$PARAMS camera:=false > "$HOUT/stack.log" 2>&1 &
  STACK=$!
  for i in $(seq 1 90); do ros2 action list 2>/dev/null | grep -q push_object && break; sleep 1; done
  python3 - "$OBJ" "$H" "$HOUT" <<'PY'
import sys, json
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from flexcell_interfaces.action import PushObject
obj, h, outdir = sys.argv[1], float(sys.argv[2]), sys.argv[3]
rclpy.init()
node = Node('sweep')
c = ActionClient(node, PushObject, 'push_object')
res = {'error': 'no server'}
if c.wait_for_server(timeout_sec=30.0):
    g = PushObject.Goal()
    g.request_id = 'sweep-%g' % h
    g.object_name = obj
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = 0.09
    g.contact_height_m = h
    g.overdrive_m = float('nan')
    f = c.send_goal_async(g)
    rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    gh = f.result()
    if gh and gh.accepted:
        rf = gh.get_result_async()
        rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
        r = rf.result().result
        res = {n: (str(getattr(r, n)) if not isinstance(getattr(r, n), (int, float, bool)) else getattr(r, n))
               for n in PushObject.Result.get_fields_and_field_types()}
json.dump(res, open(outdir + '/push.json', 'w'), indent=2)
print(json.dumps({k: res.get(k) for k in ('outcome','error_code','displacement_m','contact_made','contact_lost','increments_executed')}, indent=1))
node.destroy_node(); rclpy.shutdown()
PY
  kill -9 -$STACK 2>/dev/null || true
  kill -9 $STACK 2>/dev/null || true
  sleep 2
  python3 - "$HOUT" "$OUT" "$H" <<'PY'
import json, sys
h_out, out, h = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.load(open(h_out + '/push.json'))
    mm = float(d.get('displacement_m') or 0) * 1000
    with open(out + '/sweep.tsv', 'a') as f:
        f.write('%s\t%.2f\t%s\t%s\t%s\n' % (h, mm, d.get('outcome'),
                d.get('contact_made'), d.get('contact_lost')))
except Exception as e:
    with open(out + '/sweep.tsv', 'a') as f:
        f.write('%s\tERR\t%s\t-\t-\n' % (h, e))
PY
done
pkill -9 -f 'gz sim' 2>/dev/null || true
pkill -9 -f 'ros2 launch' 2>/dev/null || true
echo
echo '=== SWEEP RESULT ==='
column -t "$OUT/sweep.tsv" 2>/dev/null || cat "$OUT/sweep.tsv"
echo T08_SWEEP_DONE
