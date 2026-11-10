#!/bin/bash
# UNIFIED robot batch runner - replaces evobot_pair16/pair32/pair48/rerun3.
#
# WHY ONE RUNNER: four near-copies of this script drifted apart, and each new copy
# inherited a cwd trap that silently disabled a pipeline step while still producing
# plausible-looking numbers:
#   - pair48: the self-assessment never ran (relative path after cd to the sim checkout)
#   - pair48: the recovery driver never ran (same trap, one call later)
# Each time I fixed the one call I could see, not the class. This script removes the
# class: every Python invocation uses an ABSOLUTE path under $W, so cwd cannot matter,
# and the batch is validated before any number from it is reported.
#
# Usage: run_batch.sh <public_dir_name> <out_dir> <domain_base>
# NO `set -u`. Sourcing /opt/ros/jazzy/setup.bash fails under it with
# "AMENT_TRACE_SETUP_FILES: unbound variable", which silently aborted the run right
# after planning. Found by a 1-instance smoke test instead of after a 25-minute batch.
set -o pipefail
W=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
SIM=/home/ros/flexcell-p14
PUBDIR=${1:?public dir name, e.g. recovery_public48}
OUT=${2:?output dir}
DOMAIN_BASE=${3:-60}
KEYFILE=${FLEXCELL_KEY_FILE:-/home/ros/.config/flexcell/deepseek_api_key}
KEY=$(cat "$KEYFILE")
ZONES='{"zone_1":[0.12,-0.15,0.0175],"zone_2":[0.25,0.05,0.0175]}'

mkdir -p "$OUT"; chmod 777 "$OUT"

# every helper is an absolute path; none of these depend on the current directory
PLAN_B="$W/runtime/planner/prepare_baseline_b.py"
CLIENT="$W/experiments/baselines/composite_client.py"
CAPTURE="$W/benchmark/evaluators/capture_ground_truth.py"
OBSERVE="$W/benchmark/evaluators/observe_from_run.py"
SEALED="$W/benchmark/evaluators/sealed_evaluate.py"
RECOVERY="$W/runtime/recovery/recovery_driver.py"
ASSESS="$W/runtime/verifier/self_assess.py"
VALIDATE="$W/experiments/baselines/validate_batch.py"

for f in "$PLAN_B" "$CLIENT" "$CAPTURE" "$OBSERVE" "$SEALED" "$RECOVERY" "$ASSESS" "$VALIDATE"; do
  [ -f "$f" ] || { echo "FATAL: missing helper $f"; exit 3; }
done

run_one () {
  local PUB=$1 IDX=$2
  local OID; OID=$(basename "$PUB" .json)
  local D=$OUT/$OID; mkdir -p "$D"; chmod 777 "$D"
  local DOMAIN=$(( DOMAIN_BASE + IDX ))
  echo "=========== $OID (domain $DOMAIN) ==========="

  sudo -n env FLEXCELL_PILOT_API_KEY="$KEY" setpriv --reuid=1001 --regid=1001 --clear-groups \
    python3 "$PLAN_B" "$PUB" "$D" > "$D/plan.log" 2>&1
  if [ ! -f "$D/plan.json" ]; then echo "  PLAN_FAILED"; echo PLANNING > "$D/stage.txt"; return 1; fi

  pkill -9 -f "[g]z sim" 2>/dev/null; pkill -9 -f "[r]os2 launch" 2>/dev/null
  pkill -9 -f "[m]ove_group" 2>/dev/null; pkill -9 -f "[t]ask_fsm_server" 2>/dev/null
  for i in $(seq 1 30); do pgrep -f "[g]z sim|[m]ove_group|[t]ask_fsm_server" >/dev/null 2>&1 || break; sleep 1; done
  sleep 2

  source /opt/ros/jazzy/setup.bash >/dev/null 2>&1
  source /home/ros/agentic_workcell_ws/install/setup.bash >/dev/null 2>&1
  source /home/ros/flexcell-p14-ws/install/setup.bash >/dev/null 2>&1
  export GZ_PARTITION=evobot-b-$IDX RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=$DOMAIN LIBGL_ALWAYS_SOFTWARE=1
  export CYCLONEDDS_URI="file://$W/config/cyclonedds.xml"
  export FLEXCELL_REPO=$SIM FLEXCELL_WS=/home/ros/flexcell-p14-ws FLEXCELL_INSTALL=/home/ros/flexcell-p14-ws/install
  ( cd "$SIM" && python3 - "$D" <<PY
import sys
sys.path.insert(0, "/home/ros/flexcell-p14/scripts")
import sim_profile
sim_profile.profile(sys.argv[1] + "/sim", "velocity_servo", False, "legacy", 0.0, None)
PY
  )
  ros2 launch flexcell_skills trusted_sim.launch.py world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false > "$D/stack.log" 2>&1 &
  local STACK=$!
  local up=0
  for i in $(seq 1 90); do
    ros2 action list 2>/dev/null | grep -q run_composite && { up=1; break; }
    kill -0 $STACK 2>/dev/null || break
    sleep 1
  done
  if [ $up -ne 1 ]; then echo "  INFRA_STACK_DOWN"; kill -9 $STACK 2>/dev/null; echo HARNESS > "$D/stage.txt"; return 2; fi

  local NAMES; NAMES=$(python3 -c 'import json,sys;print(" ".join(o["name"] for o in json.load(open(sys.argv[1]))["objects"]))' "$PUB")

  echo "--- attempt 1 (arm B) ---"
  python3 "$CLIENT" --plan "$D/plan.json" --timeout 400 > "$D/task.out" 2>&1
  python3 "$CAPTURE" "$D/ground_truth_after1.json" $NAMES > "$D/gt1.log" 2>&1 || true
  python3 "$OBSERVE" "$D/sim" "$D/observation_after1.json" $NAMES \
    --ground-truth "$D/ground_truth_after1.json" --zones "$ZONES" > "$D/obs1.log" 2>&1 || true
  sudo -n python3 "$SEALED" --public "$PUB" --observation "$D/observation_after1.json" \
    > "$D/verdict_after1.json" 2>"$D/grade1.err" || true

  echo "--- recovery (arm R) ---"
  python3 "$RECOVERY" --run "$D" --ground-truth "$D/ground_truth_after1.json" > "$D/recovery.log" 2>&1
  if [ ! -f "$D/recovery_decision.json" ]; then
    echo "  RECOVERY_DID_NOT_RUN - aborting this run rather than reporting an inert arm"
    tail -3 "$D/recovery.log"
    echo RECOVERY_MISSING > "$D/stage.txt"
  fi
  if [ -f "$D/plan_retry.json" ]; then
    echo "--- attempt 2 ---"
    python3 "$CLIENT" --plan "$D/plan_retry.json" --timeout 400 > "$D/task_retry.out" 2>&1
  fi

  echo "--- final state ---"
  python3 "$CAPTURE" "$D/ground_truth.json" $NAMES > "$D/gt.log" 2>&1
  python3 "$OBSERVE" "$D/sim" "$D/observation.json" $NAMES \
    --ground-truth "$D/ground_truth.json" --zones "$ZONES" > "$D/obs.log" 2>&1
  kill -INT $STACK 2>/dev/null; sleep 4; kill -9 $STACK 2>/dev/null
  pkill -9 -f "[g]z sim" 2>/dev/null; pkill -9 -f "[r]os2 launch" 2>/dev/null

  echo "--- self-assessment (claim) ---"
  sudo -n env FLEXCELL_PILOT_API_KEY="$KEY" FLEXCELL_PILOT_MAX_TOKENS=32768 \
    setpriv --reuid=1001 --regid=1001 --clear-groups \
    python3 "$ASSESS" --run "$D" --spec "$PUB" --out "$D/self_assessment.json" > "$D/self_assess.log" 2>&1
  local CLAIM=""
  if [ -f "$D/self_assessment.json" ]; then
    CLAIM=$(python3 -c 'import json,sys;print("true" if json.load(open(sys.argv[1]))["success"] else "false")' "$D/self_assessment.json")
    echo "  agent claims success=$CLAIM"
  else
    echo "  SELF_ASSESS_FAILED (claim stays ABSENT, not false)"
  fi

  echo "--- grade WITH the claim ---"
  if [ -n "$CLAIM" ]; then
    python3 "$OBSERVE" "$D/sim" "$D/observation_claimed.json" $NAMES \
      --ground-truth "$D/ground_truth.json" --agent-claim "$CLAIM" --zones "$ZONES" > "$D/obs_claimed.log" 2>&1
    sudo -n python3 "$SEALED" --public "$PUB" --observation "$D/observation_claimed.json" \
      > "$D/verdict.json" 2>"$D/grade.err"
  else
    sudo -n python3 "$SEALED" --public "$PUB" --observation "$D/observation.json" \
      > "$D/verdict.json" 2>"$D/grade.err"
  fi
  python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print("  passed=",d["passed"],"claimed=",d["agent_claimed_success"],"false_success=",d["false_success"])' "$D/verdict.json" 2>/dev/null || echo "  GRADE_ERROR"
  echo DONE > "$D/stage.txt"
  return 0
}

IDX=0
LIMIT=${EVOBOT_LIMIT:-0}   # 0 = all; used for smoke tests of the runner itself
for PUB in $(ls "$W/benchmark/held_out/$PUBDIR"/*.json | sort); do
  IDX=$((IDX+1))
  if [ "$LIMIT" -gt 0 ] && [ "$IDX" -gt "$LIMIT" ]; then break; fi
  run_one "$PUB" "$IDX"
done

echo
echo "=== BATCH VALIDATION (refuses to let an inert arm be reported) ==="
python3 "$VALIDATE" "$OUT"; RC=$?
if [ $RC -ne 0 ]; then
  echo "BATCH_REJECTED: see the evidence above"; exit $RC
fi
echo BATCH_DONE
