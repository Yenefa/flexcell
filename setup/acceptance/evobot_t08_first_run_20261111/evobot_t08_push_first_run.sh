#!/usr/bin/env bash
# T08 Push -- FIRST REAL SIMULATION RUN of the push skill.
#
# WHY AN OVERLAY AND NOT AN EDIT OF THE LIVE WORKSPACE
#   The push code lives in wt-comp/src while the running stack is built from /home/ros/flexcell-p14.
#   Building into the live workspace would change the stack that Baseline A/B are measured on,
#   mid-campaign, which is exactly the kind of quiet environment change this project keeps having to
#   undo. Instead the current source is COPIED to /tmp, the push files are overlaid onto the copy,
#   and only the two affected packages are built there. The live install is never written to.
#
# WHAT COUNTS AS SUCCESS: the object's measured displacement from the simulator pose stream, graded
#   by evaluate.py v0.3.0 against the frozen T08 task. Not the skill's own report. The skill is
#   allowed to say SUCCEEDED while the object did not move; that case is a FAILURE and the grader
#   will say so.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
SRC=/home/ros/flexcell-p14/src/flexcell
OVL=/tmp/t08_push_ws
OUT=${1:-/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence/t08_push_first_run_20261111}
TASK=${2:-$WT/benchmark/tasks/t08_dev/T08-push-seed2000.json}
CONTACT_Z=${3:-0.030}
mkdir -p "$OUT"

echo '=== 1. clean overlay source from the CURRENT tree ==='
rm -rf "$OVL"; mkdir -p "$OVL/src"
cp -a "$SRC" "$OVL/src/"

echo '=== 2. overlay the push files from wt-comp (the only difference) ==='
cp -a "$WT/src/flexcell/flexcell_skills/flexcell_skills/push_server.py" \
      "$OVL/src/flexcell/flexcell_skills/flexcell_skills/"
cp -a "$WT/src/flexcell/flexcell_skills/flexcell_skills/contracts/push.py" \
      "$OVL/src/flexcell/flexcell_skills/flexcell_skills/contracts/"
mkdir -p "$OVL/src/flexcell/flexcell_skills/config"
cp -a "$WT/src/flexcell/flexcell_skills/config/push_server.yaml" \
      "$OVL/src/flexcell/flexcell_skills/config/" 2>/dev/null || true
cp -a "$WT/src/flexcell/flexcell_interfaces/action/PushObject.action" \
      "$OVL/src/flexcell/flexcell_interfaces/action/"
cp -a "$WT/src/flexcell/flexcell_interfaces/msg/CompositeStage.msg" \
      "$OVL/src/flexcell/flexcell_interfaces/msg/"
cp -a "$WT/src/flexcell/flexcell_interfaces/CMakeLists.txt" \
      "$OVL/src/flexcell/flexcell_interfaces/"
cp -a "$WT/src/flexcell/flexcell_skills/flexcell_skills/contracts/error_codes.py" \
      "$OVL/src/flexcell/flexcell_skills/flexcell_skills/contracts/"
cp -a "$WT/src/flexcell/flexcell_skills/setup.py" \
      "$OVL/src/flexcell/flexcell_skills/"
cp -a "$WT/src/flexcell/flexcell_skills/launch/week1.launch.py" \
      "$OVL/src/flexcell/flexcell_skills/launch/"
echo 'overlaid files:'
cd "$OVL" && find src -newer "$SRC/CMakeLists.txt" -name '*.py' -o -name '*.action' -o -name '*.msg' 2>/dev/null | head -12

echo '=== 3. build ONLY the two affected packages ==='
source /opt/ros/jazzy/setup.bash
cd "$OVL"
colcon build --base-paths src/flexcell --packages-select flexcell_interfaces flexcell_skills \
  --cmake-args -DCMAKE_BUILD_TYPE=Release > "$OUT/build.log" 2>&1
brc=$?
echo "colcon rc=$brc (see $OUT/build.log)"
[ "$brc" != '0' ] && { tail -25 "$OUT/build.log"; echo BUILD_FAILED; exit 3; }

echo '=== 4. bring up the stack on the base install + push overlay ==='
pkill -9 -f '[g]z sim' 2>/dev/null; pkill -9 -f '[r]os2 launch' 2>/dev/null
for n in carry_server pick_server place_server observe_server verify_server move_to_pose_server task_fsm_server move_group; do pkill -9 -f "[$n]" 2>/dev/null; done
sleep 5
source /home/ros/agentic_workcell_ws/install/setup.bash
source /home/ros/flexcell-p14-ws/install/setup.bash
source "$OVL/install/setup.bash"
export GZ_PARTITION=evobot-t08 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=${EVOBOT_ROS_DOMAIN:-180} LIBGL_ALWAYS_SOFTWARE=1
export FLEXCELL_REPO=/home/ros/flexcell-p14 FLEXCELL_WS=/home/ros/flexcell-p14-ws FLEXCELL_INSTALL=/home/ros/flexcell-p14-ws/install
python3 - "$OUT" <<PY
import sys
sys.path.insert(0, '/home/ros/flexcell-p14/scripts')
import sim_profile
params, world = sim_profile.profile(sys.argv[1] + '/sim', 'velocity_servo', False, 'legacy', 0.0, None)
print('params', params); print('world', world)
PY
PARAMS=$OUT/sim/params.yaml; WORLD=$OUT/sim/world.sdf
[ -f "$PARAMS" ] || { echo NO_PARAMS; exit 4; }
ros2 launch flexcell_skills trusted_sim.launch.py world:=$WORLD params_file:=$PARAMS camera:=false > "$OUT/stack.log" 2>&1 &
STACK=$!
for i in $(seq 1 90); do
  if ros2 action list 2>/dev/null | grep -q push_object; then echo "push_object up after ${i}s"; break; fi
  sleep 1
done
ros2 action list 2>/dev/null | grep -E 'push_object|run_composite' || echo 'ACTIONS NOT FOUND'

echo '=== 5. declare the contact height explicitly (NaN would be refused) ==='
DIR=$(python3 -c "import json;d=json.load(open('$TASK'));g=d['expected_goal']['push']['target_box_a'];print(g['direction'][0], g['direction'][1])")
DIST=$(python3 -c "import json;d=json.load(open('$TASK'));g=d['expected_goal']['push']['target_box_a'];print((g['min_displacement_m']+g['max_displacement_m'])/2)")
OBJ=$(python3 -c "import json;print(json.load(open('$TASK'))['objects'][0]['name'])")
echo "push $OBJ dir=($DIR) dist=$DIST contact_z=$CONTACT_Z"

echo '=== 6. capture BEFORE ground truth ==='
NAMES=$(python3 -c "import json;print(' '.join(o['name'] for o in json.load(open('$TASK'))['objects']))")
python3 "$WT/benchmark/evaluators/capture_ground_truth.py" "$OUT/gt_before.json" $NAMES || true

echo '=== 7. dispatch the push ==='
python3 - "$OBJ" "$DIR" "$DIST" "$CONTACT_Z" > "$OUT/push_call.json" 2>&1 <<'PY'
import sys, json
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from flexcell_interfaces.action import PushObject

# argv: <object> "<dx> <dy>" <distance_m> <contact_height_m>
obj = sys.argv[1]
dx, dy = (float(v) for v in sys.argv[2].split())
dist, cz = float(sys.argv[3]), float(sys.argv[4])

rclpy.init()
node = Node('t08_push_caller')
client = ActionClient(node, PushObject, 'push_object')
if not client.wait_for_server(timeout_sec=30.0):
    print(json.dumps({'error': 'push_object action server not available'}))
    sys.exit(2)
goal = PushObject.Goal()
goal.request_id = 't08-first-run'
goal.object_name = obj
goal.direction.x = dx
goal.direction.y = dy
goal.direction.z = 0.0
goal.distance_m = dist
goal.contact_height_m = cz
goal.overdrive_m = float('nan')
fut = client.send_goal_async(goal)
rclpy.spin_until_future_complete(node, fut, timeout_sec=60.0)
gh = fut.result()
if gh is None or not gh.accepted:
    print(json.dumps({'error': 'goal rejected'}))
    sys.exit(3)
rf = gh.get_result_async()
rclpy.spin_until_future_complete(node, rf, timeout_sec=300.0)
res = rf.result().result
out = {'success': bool(res.success), 'error_code': int(res.error_code),
       'detail': str(res.detail)}
for f in ('measured_displacement_m', 'measured_lateral_m', 'measured_dz_m',
          'arm_travel_m', 'position_error_m', 'increments_used', 'contact_lost_at_increment'):
    if hasattr(res, f):
        out[f] = getattr(res, f)
print(json.dumps(out, indent=2))
node.destroy_node(); rclpy.shutdown()
PY
cat "$OUT/push_call.json"

echo '=== 8. capture AFTER ground truth and grade independently ==='
python3 "$WT/benchmark/evaluators/capture_ground_truth.py" "$OUT/gt_after.json" $NAMES || true
python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
before = json.loads((out / 'gt_before.json').read_text())
after = json.loads((out / 'gt_after.json').read_text())
state = {'objects': {k: v for k, v in (after.get('objects') or {}).items()}}
(out / 'final_state.json').write_text(json.dumps(state, indent=2) + '\n')
print('objects observed after:', list(state['objects']))
PY
python3 "$WT/benchmark/evaluators/evaluate.py" "$TASK" "$OUT/final_state.json" > "$OUT/verdict.json" 2>&1
python3 -c "import json;d=json.load(open('$OUT/verdict.json'));print('INDEPENDENT VERDICT: passed=',d['passed'],'failed=',d['failed_clauses'])"
kill -INT $STACK 2>/dev/null; sleep 5; kill -9 $STACK 2>/dev/null
pkill -9 -f '[g]z sim' 2>/dev/null; pkill -9 -f '[r]os2 launch' 2>/dev/null
echo T08_FIRST_RUN_DONE