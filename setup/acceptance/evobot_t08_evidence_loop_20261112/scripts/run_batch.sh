#!/usr/bin/env bash
# T08 evidence-complete closed-loop push: ONE driver that runs the push policy
# AND captures the full physical evidence bundle in the same world.
#
# WHY THIS IS ONE SCRIPT AND NOT TWO
#   The previous round produced the closed-loop result (4/5 terminal passes) and
#   an earlier round produced an evidence bundle, in SEPARATE runs. Joined
#   together they would prove nothing about the same physical event, so
#   evaluate.py v0.5.0 (which requires terminal clauses AND physical evidence
#   from the SAME run) could never emit a decidable verdict. This script keeps
#   the world up across launch -> push -> ground truth -> stop, and hands the
#   resulting {objects: gt_after, evidence: bundle} to the frozen evaluator.
#
# WHAT IT DOES NOT DO
#   It does not edit sim_profile.py (the world is copied and the ContactTrace
#   plugin is injected into the COPY), does not edit push.py, push_server.py,
#   evaluate.py or any threshold, and does not tune anything on the unseen arm.
#
# USAGE
#   run_batch.sh <outdir> <arm> <task.json> <trials> <attempts> <contact_z> <guard_m>
set -u

OUT="$1"
ARM="$2"
TASK="$3"
TRIALS="$4"
ATTEMPTS="$5"
CONTACT_Z="$6"
GUARD="$7"
if [ -z "$OUT" ] || [ -z "$ARM" ] || [ -z "$TASK" ]; then
  echo "usage: run_batch.sh <outdir> <arm> <task.json> <trials> <attempts> <contact_z> <guard_m>"
  exit 2
fi

WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
SCRIPTS=$WT/setup/acceptance/evobot_t08_evidence_loop_20261112/scripts
DOMAIN=183
mkdir -p "$OUT/$ARM"

# ---------------------------------------------------------------------------
# One Gazebo at a time. The lock is held for the whole batch; the pgrep check
# is a second, independent guard so a foreign simulator is never inherited.
# ---------------------------------------------------------------------------
exec 9>/tmp/evobot_sim.lock
if ! flock -w 60 9; then
  echo "REFUSED: /tmp/evobot_sim.lock is held by another sim lane"; exit 9
fi
if pgrep -f "[g]z sim" > /dev/null 2>&1; then
  echo "REFUSED: a gz sim is already running"; pgrep -af "[g]z sim" | head -3; exit 9
fi
if pgrep -f "[e]vobot_batch_v2_gated" > /dev/null 2>&1; then
  echo "REFUSED: gated batch running"; exit 9
fi

set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash 2>/dev/null
source /home/ros/flexcell-p14-ws/install/setup.bash 2>/dev/null
source /tmp/t08_push_ws/install/setup.bash 2>/dev/null
# APPEND, never assign: assigning erases ROS's own Python path and the symptom
# is 'No module named sensor_msgs', which looks like a code bug and is not one.
export PYTHONPATH="$WT/src/flexcell/flexcell_skills:$PYTHONPATH"
set -u
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID="$DOMAIN"
export GZ_PARTITION=evobot-t08loop
export LIBGL_ALWAYS_SOFTWARE=1

GIT_HEAD=$(git -C "$WT" rev-parse HEAD 2>/dev/null || echo UNKNOWN)
GZ_VERSION=$(gz sim --versions 2>/dev/null | head -1 || echo UNKNOWN)
ROS_DISTRO=$(ls /opt/ros 2>/dev/null | head -1 || echo UNKNOWN)

echo "=== interface preflight (never guess a ROS field) ==="
python3 "$WT/benchmark/tools/check_ros_interfaces.py" > "$OUT/$ARM/interface_check.log" 2>&1 \
  || { echo "INTERFACE_CHECK_FAILED"; tail -20 "$OUT/$ARM/interface_check.log"; exit 1; }
echo "interface check OK"

echo "=== policy / driver fingerprints (frozen before arm U) ==="
{
  echo "git_head $GIT_HEAD"
  echo "ros_distro $ROS_DISTRO"
  echo "gz_version $GZ_VERSION"
  echo "ros_domain_id $DOMAIN"
  echo "contact_height_m $CONTACT_Z"
  echo "max_attempts $ATTEMPTS"
  echo "ceiling_guard_m $GUARD"
  echo "task $TASK"
  echo "task_sha256 $(sha256sum "$TASK" | cut -d' ' -f1)"
  echo "trials $TRIALS"
  echo "arm $ARM"
  sha256sum "$WT/src/flexcell/flexcell_skills/flexcell_skills/contracts/push_recover.py"
  sha256sum "$WT/src/flexcell/flexcell_skills/flexcell_skills/contracts/push.py"
  sha256sum "$WT/src/flexcell/flexcell_skills/flexcell_skills/push_server.py"
  sha256sum "$WT/benchmark/evaluators/evaluate.py"
  sha256sum "$WT/benchmark/evidence/recorder.py"
  sha256sum "$WT/benchmark/evidence/verify.py"
  sha256sum "$WT/benchmark/evidence/schema.py"
  sha256sum /home/ros/flexcell-p14/scripts/sim_profile.py
  sha256sum "$SCRIPTS/run_evidence_push.py"
  sha256sum "$SCRIPTS/build_trial_evidence.py"
  sha256sum "$SCRIPTS/inject_contact_evidence.py"
} > "$OUT/$ARM/manifest.txt"
cat "$OUT/$ARM/manifest.txt"

cleanup_stack() {
  # Process-group kill first, then bracket-pattern pkill. The bracket trick
  # keeps the pattern from matching this script's own command line.
  if [ -n "$STACK" ]; then
    kill -9 -"$STACK" 2>/dev/null || true
    kill -9 "$STACK" 2>/dev/null || true
  fi
  for pat in "[g]z sim" "[r]os2 launch" "[p]ush_server" "[p]arameter_bridge" \
             "[r]obot_state_publisher" "[m]ove_group" "[c]arry_server" "[p]ick_server" \
             "[p]lace_server" "[o]bserve_server" "[v]erify_server" "[t]ask_fsm_server" \
             "[m]ove_to_pose_server" "[m]tc_planner" "[r]viz2"; do
    pkill -9 -f "$pat" 2>/dev/null || true
  done
  STACK=""
}

STACK=""
trap 'cleanup_stack' EXIT

for T in $(seq 1 "$TRIALS"); do
  D="$OUT/$ARM/t$T"
  mkdir -p "$D/logs"
  rm -rf "$D/sim"
  echo
  echo "=== arm $ARM trial $T -> $D ==="

  LOAD_BEFORE=$(cut -d' ' -f1-3 /proc/loadavg)
  START_NS=$(date +%s%N)

  cleanup_stack
  sleep 3
  if pgrep -f "[g]z sim" > /dev/null 2>&1; then
    echo "REFUSED: a gz sim survived cleanup"; pgrep -af "[g]z sim" | head -3
    echo "INVALID_INFRA gz_survived_cleanup" > "$D/invalid_infra.txt"
    continue
  fi

  # --- 1. world: generated by sim_profile (untouched), then copied ---------
  if ! python3 - "$D" <<'PY' > "$D/logs/sim_profile.log" 2>&1
import sys
sys.path.insert(0, "/home/ros/flexcell-p14/scripts")
import sim_profile
params, world = sim_profile.profile(sys.argv[1] + "/sim", "velocity_servo",
                                    False, "legacy", 0.0, None)
print("params", params)
print("world", world)
PY
  then
    echo "INVALID_INFRA sim_profile_failed"; tail -20 "$D/logs/sim_profile.log"
    echo "INVALID_INFRA sim_profile_failed" > "$D/invalid_infra.txt"
    continue
  fi
  WORLD="$D/sim/world.sdf"
  PARAMS="$D/sim/params.yaml"
  if [ ! -f "$WORLD" ]; then
    echo "INVALID_INFRA no_world"; echo "INVALID_INFRA no_world" > "$D/invalid_infra.txt"; continue
  fi

  # --- 2. contact evidence channel into the COPY ---------------------------
  if ! python3 "$SCRIPTS/inject_contact_evidence.py" "$WORLD" > "$D/logs/inject.log" 2>&1; then
    echo "INVALID_INFRA injection_failed"; tail -20 "$D/logs/inject.log"
    echo "INVALID_INFRA injection_failed" > "$D/invalid_infra.txt"
    continue
  fi
  grep -c "flexcell::ContactTrace" "$WORLD" > "$D/logs/contact_trace_count.txt" 2>/dev/null || true

  # --- 3. launch with the step logs enabled --------------------------------
  export FLEXCELL_CONTACT_STEP_LOG="$D/logs/contact_steps.jsonl"
  export FLEXCELL_PHYSICS_STEP_LOG="$D/logs/physics_steps.jsonl"
  rm -f "$FLEXCELL_CONTACT_STEP_LOG" "$FLEXCELL_PHYSICS_STEP_LOG"
  setsid ros2 launch flexcell_skills trusted_sim.launch.py \
      world:="$WORLD" params_file:="$PARAMS" camera:=false \
      > "$D/logs/stack.log" 2>&1 &
  STACK=$!
  UP=0
  for i in $(seq 1 120); do
    if ros2 action list 2>/dev/null | grep -q push_object; then UP=1; echo "  push_object up after $i s"; break; fi
    if ! kill -0 "$STACK" 2>/dev/null; then echo "  stack died"; break; fi
    sleep 1
  done
  if [ "$UP" -ne 1 ]; then
    echo "  INVALID_INFRA push_object server never appeared"
    echo "INVALID_INFRA push_object_unavailable" > "$D/invalid_infra.txt"
    cleanup_stack; sleep 2
    continue
  fi
  sleep 3

  # --- 4. joint-state recorder (gripper gate needs the whole span) ---------
  python3 - "$D/logs/joint_states.jsonl" > "$D/logs/joints.log" 2>&1 <<'PY' &
import sys, json, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
path = sys.argv[1]
rclpy.init()
node = Node("t08_loop_joint_recorder")
stream = open(path, "w")
def on_state(msg):
    stream.write(json.dumps({"monotonic_ns": time.monotonic_ns(),
                             "name": list(msg.name),
                             "position": [float(v) for v in msg.position]}) + "\n")
    stream.flush()
node.create_subscription(JointState, "/joint_states", on_state, 50)
deadline = time.monotonic() + 240.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
stream.close(); node.destroy_node()
if rclpy.ok(): rclpy.shutdown()
PY
  JOINTS=$!

  # --- 5. ground truth BEFORE (the world's own poses, not a claim) --------
  python3 - "$TASK" "$D/gt_before.json" <<'PY' > "$D/logs/gt_before.log" 2>&1 || true
import sys, json
from flexcell_skills.common import sample_gz_pose
spec = json.load(open(sys.argv[1], encoding="utf-8"))
out = {"source": "GZ_GROUND_TRUTH", "objects": {}, "errors": {}}
for obj in spec["objects"]:
    pose, err = sample_gz_pose(obj["name"], timeout_s=8.0)
    if pose is None:
        out["errors"][obj["name"]] = err
        continue
    out["objects"][obj["name"]] = [round(float(v), 6) for v in pose[0]] + [0.0]
json.dump(out, open(sys.argv[2], "w"), indent=2)
print("captured %d/%d" % (len(out["objects"]), len(spec["objects"])))
PY

  # --- 6. the push itself: closed loop (or single shot) -------------------
  python3 "$SCRIPTS/run_evidence_push.py" "$TASK" "$D" "$CONTACT_Z" "$ATTEMPTS" "$GUARD" \
      > "$D/logs/driver.log" 2>&1
  DRIVER_RC=$?
  cat "$D/logs/driver.log"
  if [ "$DRIVER_RC" -ne 0 ]; then
    echo "  driver rc=$DRIVER_RC"
  fi

  # --- 7. ground truth AFTER, still inside the live world -----------------
  sleep 2
  python3 - "$TASK" "$D/gt_after.json" <<'PY' > "$D/logs/gt_after.log" 2>&1
import sys, json
from flexcell_skills.common import sample_gz_pose
spec = json.load(open(sys.argv[1], encoding="utf-8"))
out = {"source": "GZ_GROUND_TRUTH", "objects": {}, "errors": {}}
for obj in spec["objects"]:
    pose, err = sample_gz_pose(obj["name"], timeout_s=8.0)
    if pose is None:
        out["errors"][obj["name"]] = err
        continue
    out["objects"][obj["name"]] = [round(float(v), 6) for v in pose[0]] + [0.0]
json.dump(out, open(sys.argv[2], "w"), indent=2)
print("captured %d/%d" % (len(out["objects"]), len(spec["objects"])))
PY
  cat "$D/logs/gt_after.log"

  # --- 8. stop the stack, then let the recorder finish --------------------
  kill -INT "$JOINTS" 2>/dev/null || true
  cleanup_stack
  sleep 3
  wait "$JOINTS" 2>/dev/null || true

  LOAD_AFTER=$(cut -d' ' -f1-3 /proc/loadavg)
  END_NS=$(date +%s%N)
  WALL_S=$(awk -v a="$START_NS" -v b="$END_NS" 'BEGIN{printf "%.1f", (b-a)/1e9}')

  # --- 9. preview slices (the FULL data stays in the logs + bundle) -------
  for pair in physics_steps contact_steps joint_states; do
    src="$D/logs/$pair.jsonl"
    dst="$D/$pair"'_sample.jsonl'
    if [ -f "$src" ]; then head -200 "$src" > "$dst"; fi
  done

  # --- 10. bundle + independent max_z + frozen evaluator -----------------
  python3 "$SCRIPTS/build_trial_evidence.py" \
      "$D" "$TASK" "t08loop-$ARM-t$T" "$ARM" "$T" "$WALL_S" \
      "$LOAD_BEFORE" "$LOAD_AFTER" "$GIT_HEAD" "$GZ_VERSION" "$ROS_DISTRO" \
      "$DOMAIN" "$CONTACT_Z" > "$D/logs/evidence.log" 2>&1
  EV_RC=$?
  if [ "$EV_RC" -ne 0 ]; then
    echo "  EVIDENCE_BUILD_FAILED rc=$EV_RC"; tail -30 "$D/logs/evidence.log"
    echo "INVALID_INFRA evidence_build_failed" > "$D/invalid_infra.txt"
  else
    grep -o 'TRIAL_RECORD .*' "$D/logs/evidence.log" | head -1
  fi

  # --- 11. orphan check ---------------------------------------------------
  ORPHANS=$(pgrep -af '[g]z sim|[p]arameter_bridge|[r]obot_state_publisher|[c]omposite_server|[p]ush_server' | wc -l)
  echo "  orphans=$ORPHANS"
  echo "$ORPHANS" > "$D/logs/orphans.txt"
  if [ "$ORPHANS" -ne 0 ]; then
    pgrep -af '[g]z sim|[p]arameter_bridge|[r]obot_state_publisher|[c]omposite_server|[p]ush_server' | head -5
  fi
done

cleanup_stack
echo
echo "=== arm $ARM done ==="
echo "orphans: $(pgrep -af '[g]z sim|[p]arameter_bridge|[r]obot_state_publisher|[c]omposite_server|[p]ush_server' | wc -l)"
echo T08_EVIDENCE_LOOP_ARM_DONE
