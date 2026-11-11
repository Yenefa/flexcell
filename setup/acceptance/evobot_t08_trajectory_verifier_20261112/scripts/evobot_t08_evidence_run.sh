#!/usr/bin/env bash
# Capture a REAL T08 push with every evidence channel the verifier needs.
#
# WHY THE WORLD IS POST-PROCESSED INSTEAD OF sim_profile BEING EDITED
#   sim_profile.py:85 refuses contact_trace outside the detachable_joint 2 ms
#   profile, and T08 push runs on velocity_servo. Editing sim_profile would
#   change a file whose output is hashed into frozen declarations, which is
#   exactly the kind of quiet environment change this project keeps having to
#   undo. So the generated world.sdf is copied and the ContactTrace plugin is
#   injected into the COPY. sim_profile.py stays byte-identical.
#
# WHAT THIS PROVES AND WHAT IT DOES NOT
#   It produces real physics telemetry from a real Gazebo run. It does not
#   make the robot pass T08: the skill saturates at ~28.5 mm against a 30 mm
#   gate, and that threshold is frozen. A failed terminal clause is recorded
#   as such and the verifier must report it, not explain it away.

# ROS setup.bash reads unset variables, so nounset must be OFF while sourcing.
set +u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
CI=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts
OUT=${1:?output directory required}
TASK=${2:-$WT/benchmark/tasks/t08_dev/T08-push-seed2000.json}
CONTACT_Z=${3:-0.030}
DOMAIN=${4:-47}

if pgrep -f "evobot_batch_v2_gated" > /dev/null 2>&1; then
  echo "REFUSED: gated batch running"; exit 9
fi
if pgrep -f "[g]z sim" > /dev/null 2>&1; then
  echo "REFUSED: a gz sim is already running"; pgrep -af "[g]z sim" | head -3; exit 9
fi

rm -rf "$OUT"; mkdir -p "$OUT/logs"

source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash 2>/dev/null
source /home/ros/flexcell-p14-ws/install/setup.bash 2>/dev/null
if [ -f /tmp/t08_push_ws/install/setup.bash ]; then
  source /tmp/t08_push_ws/install/setup.bash
fi
export ROS_DOMAIN_ID="$DOMAIN" RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export GZ_PARTITION=evobot-t08ev LIBGL_ALWAYS_SOFTWARE=1
export PYTHONPATH="$WT/src/flexcell/flexcell_skills:${PYTHONPATH:-}"

echo "=== 1. generate the velocity_servo world (sim_profile untouched) ==="
python3 - "$OUT" <<PY
import sys
sys.path.insert(0, "/home/ros/flexcell-p14/scripts")
import sim_profile
params, world = sim_profile.profile(sys.argv[1] + "/sim", "velocity_servo",
                                   False, "legacy", 0.0, None)
print("params", params); print("world", world)
PY
WORLD=$OUT/sim/world.sdf
PARAMS=$OUT/sim/params.yaml
[ -f "$WORLD" ] || { echo NO_WORLD; exit 4; }

echo "=== 2. inject the contact evidence channel into the COPY ==="
python3 - "$WORLD" <<PY
import sys, xml.etree.ElementTree as ET
path = sys.argv[1]
tree = ET.parse(path)
world = tree.getroot()
if world.tag != "sdf":
    raise SystemExit("unexpected root " + world.tag)
w = world.find("world")
# Names must be present for the contact partner identity to be readable;
# without this the contacts carry ids only and the pusher cannot be named.
physics = w.find("plugin[@name='gz::sim::systems::Physics']")
if physics is None:
    raise SystemExit("physics system plugin missing")
if physics.find("contacts_entity_names") is None:
    ET.SubElement(physics, "contacts_entity_names").text = "true"
observer = ET.SubElement(w, "plugin", name="flexcell::ContactTrace",
                          filename="libflexcell_contact_trace.so")
for model in ("target_box_a", "target_box_b"):
    watch = ET.SubElement(observer, "watch")
    for key, value in (("model", model), ("link", "link"), ("collision", "col")):
        ET.SubElement(watch, key).text = value
# The floor is watched too so that table support is a MEASURED contact,
# not an inference from the object sitting at a plausible height.
floor = ET.SubElement(observer, "watch")
for key, value in (("model", "ground_plane"), ("link", "link"),
                   ("collision", "collision")):
    ET.SubElement(floor, key).text = value
ET.SubElement(observer, "flush_each_step").text = "true"
# The contact component only exists if the collision has a contact sensor.
for model in ("target_box_a", "target_box_b"):
    link = w.find("model[@name='%s']/link[@name='link']" % model)
    if link is None:
        raise SystemExit("missing link for " + model)
    if link.find("sensor[@type='contact']") is None:
        sensor = ET.SubElement(link, "sensor", name="contact_probe", type="contact")
        ET.SubElement(sensor, "always_on").text = "true"
        ET.SubElement(sensor, "update_rate").text = "500"
        ET.SubElement(ET.SubElement(sensor, "contact"), "collision").text = "col"
tree.write(path, encoding="utf-8", xml_declaration=True)
print("injected ContactTrace + contacts_entity_names + contact sensors")
PY
grep -c ContactTrace "$WORLD" || { echo INJECTION_FAILED; exit 4; }

echo "=== 3. launch with step logs enabled ==="
# The plugins write their logs from inside the physics loop; these paths are
# the only way to get per-step evidence rather than sampled evidence.
export FLEXCELL_CONTACT_STEP_LOG="$OUT/logs/contact_steps.jsonl"
export FLEXCELL_PHYSICS_STEP_LOG="$OUT/logs/physics_steps.jsonl"
rm -f "$FLEXCELL_CONTACT_STEP_LOG" "$FLEXCELL_PHYSICS_STEP_LOG"
setsid ros2 launch flexcell_skills trusted_sim.launch.py \
    world:=$WORLD params_file:=$PARAMS camera:=false > "$OUT/logs/stack.log" 2>&1 &
STACK=$!
STACK_PGID=$STACK
for i in $(seq 1 90); do
  if ros2 action list 2>/dev/null | grep -q push_object; then
    echo "push_object up after ${i}s"; break
  fi
  sleep 1
done
ls -la "$FLEXCELL_CONTACT_STEP_LOG" "$FLEXCELL_PHYSICS_STEP_LOG" 2>/dev/null || true

echo "=== 4. capture joint states throughout ==="
python3 - "$OUT/logs/joint_states.jsonl" > "$OUT/logs/joints.log" 2>&1 <<PY &
import sys, json, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
path = sys.argv[1]
rclpy.init()
node = Node("t08_evidence_joint_recorder")
stream = open(path, "w")
def on_state(msg):
    stream.write(json.dumps({
        "monotonic_ns": time.monotonic_ns(),
        "name": list(msg.name),
        "position": [float(v) for v in msg.position],
    }) + "\n")
    stream.flush()
node.create_subscription(JointState, "/joint_states", on_state, 50)
deadline = time.monotonic() + 200.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
stream.close(); node.destroy_node()
if rclpy.ok(): rclpy.shutdown()
PY
JOINTS=$!
sleep 3

echo "=== 5. dispatch the push ==="
OBJ=$(python3 -c "import json;print(json.load(open('$TASK'))['objects'][0]['name'])")
DIR=$(python3 -c "import json;d=json.load(open('$TASK'));g=d['expected_goal']['push']['$OBJ'];print(g['direction'][0], g['direction'][1])")
DIST=$(python3 -c "import json;d=json.load(open('$TASK'));g=d['expected_goal']['push']['$OBJ'];print((g['min_displacement_m']+g['max_displacement_m'])/2)")
echo "push $OBJ dir=($DIR) dist=$DIST contact_z=$CONTACT_Z"
python3 - "$OBJ" "$DIR" "$DIST" "$CONTACT_Z" > "$OUT/push_call.json" 2>&1 <<PY
import sys, json
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from flexcell_interfaces.action import PushObject
obj = sys.argv[1]
dx, dy = (float(v) for v in sys.argv[2].split())
dist, cz = float(sys.argv[3]), float(sys.argv[4])
rclpy.init()
node = Node("t08_evidence_push_caller")
client = ActionClient(node, PushObject, "push_object")
if not client.wait_for_server(timeout_sec=30.0):
    print(json.dumps({"error": "push_object unavailable"})); sys.exit(2)
goal = PushObject.Goal()
goal.request_id = "t08-evidence"
goal.object_name = obj
goal.direction.x, goal.direction.y, goal.direction.z = dx, dy, 0.0
goal.distance_m = dist
goal.contact_height_m = cz
goal.overdrive_m = float("nan")
future = client.send_goal_async(goal)
rclpy.spin_until_future_complete(node, future, timeout_sec=60.0)
handle = future.result()
if handle is None or not handle.accepted:
    print(json.dumps({"error": "rejected"})); sys.exit(3)
result_future = handle.get_result_async()
rclpy.spin_until_future_complete(node, result_future, timeout_sec=300.0)
result = result_future.result().result
def plain(value):
    if isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "x"):
        return [float(getattr(value, a)) for a in ("x", "y", "z")]
    return str(value)
out = {n: plain(getattr(result, n))
       for n in PushObject.Result.get_fields_and_field_types()}
print(json.dumps(out, indent=2))
node.destroy_node(); rclpy.shutdown()
PY
cat "$OUT/push_call.json"

echo "=== 6. ground truth before/after ==="
NAMES=$(python3 -c "import json;print(' '.join(o['name'] for o in json.load(open('$TASK'))['objects']))")
sleep 2
kill -INT $JOINTS 2>/dev/null; wait $JOINTS 2>/dev/null
python3 "$WT/benchmark/evaluators/capture_ground_truth.py" "$OUT/gt_after.json" $NAMES || true

echo "=== 7. stop the stack ==="
kill -INT $STACK 2>/dev/null; sleep 5
kill -9 -"$STACK_PGID" 2>/dev/null || true
for pat in "[g]z sim" "[r]os2 launch" "[c]arry_server" "[p]ick_server" "[p]lace_server" "[o]bserve_server" "[v]erify_server" "[m]ove_to_pose_server" "[t]ask_fsm_server" "[m]ove_group" "[p]arameter_bridge" "[r]obot_state_publisher" "[p]ush_server"; do
  pkill -9 -f "$pat" 2>/dev/null || true
done

echo "=== 8. what evidence did the plugins write? ==="
wc -l "$FLEXCELL_CONTACT_STEP_LOG" "$FLEXCELL_PHYSICS_STEP_LOG" "$OUT/logs/joint_states.jsonl" 2>/dev/null
echo EVOBOT_T08_EVIDENCE_DONE
