#!/usr/bin/env bash
# T08 at the block's centre height with the overdrive controlled.
#
# PRE-REGISTERED in README.md before this ran. Two changes from the evidence loop
# (which used contact_height_m = 0.0200, overdrive = default):
#   contact_height_m : 0.0200 -> 0.0175   (block centre)
#   overdrive_m      : nan    -> 0.005
# Everything else identical. One push, dev instance, tuning allowed.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
OUT=${1:-/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence/t08_centre_height_20261112}
TASK=$WT/benchmark/tasks/t08_dev/T08-push-seed2000.json
H=0.0175
OVR=0.005
DIST=0.09
mkdir -p "$OUT"

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
source /tmp/t08_push_ws/install/setup.bash
set -u
export GZ_PARTITION=evobot-t08 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=${EVOBOT_ROS_DOMAIN:-180} LIBGL_ALWAYS_SOFTWARE=1

OBJ=$(python3 -c "import json;print(json.load(open('$TASK'))['objects'][0]['name'])")
echo "object=$OBJ contact_height=$H overdrive=$OVR distance=$DIST"

pkill -9 -f 'gz sim' 2>/dev/null || true
pkill -9 -f 'ros2 launch' 2>/dev/null || true
pkill -9 -f 'push_server' 2>/dev/null || true
pkill -9 -f 'parameter_bridge' 2>/dev/null || true
pkill -9 -f 'robot_state_publisher' 2>/dev/null || true
sleep 4

rm -rf "$OUT/sim"
python3 - "$OUT" <<PY
import sys
sys.path.insert(0, '/home/ros/flexcell-p14/scripts')
import sim_profile
params, world = sim_profile.profile(sys.argv[1] + '/sim', 'velocity_servo', False, 'legacy', 0.0, None)
print(params); print(world)
PY
PARAMS=$OUT/sim/params.yaml
WORLD=$OUT/sim/world.sdf
setsid ros2 launch flexcell_skills trusted_sim.launch.py world:=$WORLD params_file:=$PARAMS camera:=false > "$OUT/stack.log" 2>&1 &
STACK=$!
SERVER_UP=0
for i in $(seq 1 120); do
  if ros2 action list 2>/dev/null | grep -q push_object; then SERVER_UP=1; break; fi
  sleep 1
done
if [ "$SERVER_UP" -ne 1 ]; then
  echo "HARNESS_ERROR: push_object action server never appeared; NOT a measurement"
  echo "HARNESS_ERROR" > "$OUT/verdict.txt"
  kill -9 -$STACK 2>/dev/null || true
  kill -9 $STACK 2>/dev/null || true
  exit 3
fi
echo "push_object up after ${i}s"

python3 - "$OBJ" "$H" "$OVR" "$DIST" "$OUT" <<'PY'
import sys, json
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from flexcell_interfaces.action import PushObject
obj, h, ovr, dist, outdir = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
rclpy.init()
node = Node('centre_height')
c = ActionClient(node, PushObject, 'push_object')
res = {'error': 'no server'}
if c.wait_for_server(timeout_sec=30.0):
    g = PushObject.Goal()
    g.request_id = 'centre-height-1'
    g.object_name = obj
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = dist
    g.contact_height_m = h
    g.overdrive_m = ovr
    f = c.send_goal_async(g)
    rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    gh = f.result()
    if gh and gh.accepted:
        rf = gh.get_result_async()
        rclpy.spin_until_future_complete(node, rf, timeout_sec=300.0)
        r = rf.result().result
        res = {n: (getattr(r, n) if isinstance(getattr(r, n), (int, float, bool)) else str(getattr(r, n)))
               for n in PushObject.Result.get_fields_and_field_types()}
json.dump(res, open(outdir + '/push.json', 'w'), indent=2)
print(json.dumps({k: res.get(k) for k in ('outcome','error_code','displacement_m','direction_cos','delta_z_m','contact_made','contact_lost','increments_executed','requested_distance_m','detail')}, indent=1))
node.destroy_node(); rclpy.shutdown()
PY

kill -9 -$STACK 2>/dev/null || true
kill -9 $STACK 2>/dev/null || true
sleep 2
pkill -9 -f 'gz sim' 2>/dev/null || true
pkill -9 -f 'ros2 launch' 2>/dev/null || true
pkill -9 -f 'push_server' 2>/dev/null || true
echo '=== done ==='
