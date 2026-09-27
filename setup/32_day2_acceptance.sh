#!/usr/bin/env bash
# FlexCell Day-2 acceptance battery — upstream cases per docs/DAY2_MOVETOPOSE.md
# Usage (from Windows): wsl -d Ubuntu-24.04 -u ros -- bash -c 'tr -d "\r" < /mnt/f/flexcell-stage/setup/32_day2_acceptance.sh > /tmp/d2.sh && bash /tmp/d2.sh happy_a happy_b'
# NOTE: no "set -u" here — ROS setup.bash reads unbound vars (AMENT_TRACE_SETUP_FILES) and dies.
cd /home/ros/agentic_workcell_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py
P=plan_execute.py
E=/mnt/f/flexcell-stage/setup/acceptance/day2
mkdir -p "$E"

if ! pgrep -f move_to_pose_server > /dev/null; then
  echo "FATAL: move_to_pose_server not running" >&2
  exit 9
fi

case_happy_a() {
  { echo "=== case1 happy_a target=(0.20,0.05,0.20) q=(0,0,0,1) profile=demo_slow | $(date -Is) | EXPECT: outcome=SUCCEEDED pos_err<0.02 execution_started=true ==="
    timeout 90 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --request-id case1_happy_a
    echo "RC=$?"
  } 2>&1 | tee "$E/01_happy_a.out"
}

case_happy_b() {
  { echo "=== case2 happy_b target=(0.15,-0.15,0.25) q=(0,0,0,1) profile=demo_slow | $(date -Is) | EXPECT: outcome=SUCCEEDED pos_err<0.02 ==="
    timeout 90 python3 "$C" --pose 0.15 -0.15 0.25 0 0 0 1 --request-id case2_happy_b
    echo "RC=$?"
  } 2>&1 | tee "$E/02_happy_b.out"
}

case_invalid_workspace() {
  { echo "=== case3 invalid_workspace target=(0,0,0.90) z>0.75 | $(date -Is) | EXPECT: outcome=FAILED error_code=INVALID_GOAL execution_started=false ==="
    timeout 30 python3 "$C" --pose 0.0 0.0 0.90 0 0 0 1 --request-id case3_invalid_ws
    echo "RC=$?"
  } 2>&1 | tee "$E/03_invalid_workspace.out"
}

case_invalid_quat() {
  { echo "=== case4 invalid_quat q=(0,0,0,0.5) non-normalized | $(date -Is) | EXPECT: INVALID_GOAL ==="
    timeout 30 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 0.5 --request-id case4_invalid_quat
    echo "RC=$?"
  } 2>&1 | tee "$E/04_invalid_quat.out"
}

case_invalid_profile() {
  { echo "=== case5 invalid_profile profile=turbo not whitelisted | $(date -Is) | EXPECT: INVALID_GOAL ==="
    timeout 30 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --profile turbo --request-id case5_invalid_profile
    echo "RC=$?"
  } 2>&1 | tee "$E/05_invalid_profile.out"
}

case_stale_world() {
  { echo "=== case6 stale_world expected_revision=7 with gate off | $(date -Is) | EXPECT: error_code=STALE_WORLD execution_started=false ==="
    timeout 30 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --expected-revision 7 --request-id case6_stale_world
    echo "RC=$?"
  } 2>&1 | tee "$E/06_stale_world.out"
}

case_ik_unreachable() {
  { echo "=== case7 ik_unreachable target=(0.42,0,0.10) inside box beyond reach | $(date -Is) | EXPECT: error_code=IK_UNREACHABLE execution_started=false fast-fail~1s ==="
    timeout 60 python3 "$C" --pose 0.42 0.0 0.10 0 0 0 1 --request-id case7_ik_unreachable
    echo "RC=$?"
  } 2>&1 | tee "$E/07_ik_unreachable.out"
}

case_timeout() {
  { echo "=== case8 timeout deadline=800ms on far target (0.25,0.15,0.15) | $(date -Is) | EXPECT: error_code=EXECUTION_TIMEOUT preempted=true stop_confirmed=true phases include STOPPING ==="
    timeout 90 python3 "$C" --pose 0.25 0.15 0.15 0 0 0 1 --deadline 800 --request-id case8_timeout
    echo "RC=$?"
  } 2>&1 | tee "$E/08_timeout.out"
}

case_cancel() {
  { echo "=== case9 cancel 1.0s into EXECUTING, target=(0.05,-0.28,0.18) | $(date -Is) | EXPECT: outcome=CANCELED preempted=true stop_confirmed=true ==="
    timeout 90 python3 "$C" --pose 0.05 -0.28 0.18 0 0 0 1 --cancel-after-executing 1.0 --request-id case9_cancel
    echo "RC=$?"
  } 2>&1 | tee "$E/09_cancel.out"
}

case_regression() {
  { echo "=== case10 day1_regression plan_execute.py 0.0 -0.9 0.9 0.5 | $(date -Is) | EXPECT: PLAN/EXECUTE error_code=1 MOTION_DETECTED=True ==="
    timeout 120 python3 "$P" 0.0 -0.9 0.9 0.5
    echo "RC=$?"
  } 2>&1 | tee "$E/10_day1_regression.out"
}

for c in "$@"; do
  "case_$c"
done
