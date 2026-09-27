#!/usr/bin/env bash
# FlexCell Day-2 acceptance battery — upstream cases per docs/DAY2_MOVETOPOSE.md
# Usage: bash 32_day2_acceptance.sh happy_a happy_b invalid_workspace ... regression
#        (an explicit case list is REQUIRED - bare invocation was a silent
#        no-op in the old version and once produced a 13-byte "regress" artifact)
#
# Audit P1-5: every case ends in a HARD GATE; the battery exits non-zero when
# any gate failed (MOTION_DETECTED=False used to print yet still exit 0).
# Audit P1-7: artifacts land in a versioned session dir, never overwritten.
# Precondition: move_to_pose_server running; for case8/9 the arm should be
# away from the case targets (e.g. right after a reset or a demo) so the
# 800ms deadline / 1.0s cancel triggers have real motion to interrupt.
#
# Machine overrides: FLEXCELL_WS / FLEXCELL_STAGE (see lib_gate.sh).
source "$(dirname "$0")/lib_gate.sh"
cd "$(_flexcell_ws)"
source /opt/ros/jazzy/setup.bash
source install/setup.bash
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py
P=plan_execute.py
gate_init day2_battery
E="$GATE_SESSION"

if ! pgrep -f move_to_pose_server > /dev/null; then
  echo "FATAL: move_to_pose_server not running" >&2
  exit 9
fi

case_happy_a() {
  { echo "=== case1 happy_a target=(0.20,0.05,0.20) q=(0,0,0,1) profile=demo_slow | $(date -Is) | EXPECT: outcome=SUCCEEDED pos_err<0.02 execution_started=true ==="
    timeout 90 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --request-id case1_happy_a
    echo "RC=$?"
  } 2>&1 | tee "$E/01_happy_a.out"
  gate_check happy_a_outcome "$E/01_happy_a.out" '"outcome": "OUTCOME_SUCCEEDED"'
  gate_check happy_a_started "$E/01_happy_a.out" '"execution_started": true'
  gate_num_lt happy_a_pos_err "$E/01_happy_a.out" position_error_m 0.02
}

case_happy_b() {
  { echo "=== case2 happy_b target=(0.15,-0.15,0.25) q=(0,0,0,1) profile=demo_slow | $(date -Is) | EXPECT: outcome=SUCCEEDED pos_err<0.02 ==="
    timeout 90 python3 "$C" --pose 0.15 -0.15 0.25 0 0 0 1 --request-id case2_happy_b
    echo "RC=$?"
  } 2>&1 | tee "$E/02_happy_b.out"
  gate_check happy_b_outcome "$E/02_happy_b.out" '"outcome": "OUTCOME_SUCCEEDED"'
  gate_num_lt happy_b_pos_err "$E/02_happy_b.out" position_error_m 0.02
}

case_invalid_workspace() {
  { echo "=== case3 invalid_workspace target=(0,0,0.90) z>0.75 | $(date -Is) | EXPECT: outcome=FAILED error_code=INVALID_GOAL execution_started=false ==="
    timeout 30 python3 "$C" --pose 0.0 0.0 0.90 0 0 0 1 --request-id case3_invalid_ws
    echo "RC=$?"
  } 2>&1 | tee "$E/03_invalid_workspace.out"
  gate_check invalid_ws_code "$E/03_invalid_workspace.out" '"error_code": "ERR_INVALID_GOAL"'
  gate_check invalid_ws_not_started "$E/03_invalid_workspace.out" '"execution_started": false'
}

case_invalid_quat() {
  { echo "=== case4 invalid_quat q=(0,0,0,0.5) non-normalized | $(date -Is) | EXPECT: INVALID_GOAL ==="
    timeout 30 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 0.5 --request-id case4_invalid_quat
    echo "RC=$?"
  } 2>&1 | tee "$E/04_invalid_quat.out"
  gate_check invalid_quat_code "$E/04_invalid_quat.out" '"error_code": "ERR_INVALID_GOAL"'
}

case_invalid_profile() {
  { echo "=== case5 invalid_profile profile=turbo not whitelisted | $(date -Is) | EXPECT: INVALID_GOAL ==="
    timeout 30 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --profile turbo --request-id case5_invalid_profile
    echo "RC=$?"
  } 2>&1 | tee "$E/05_invalid_profile.out"
  gate_check invalid_profile_code "$E/05_invalid_profile.out" '"error_code": "ERR_INVALID_GOAL"'
}

case_stale_world() {
  { echo "=== case6 stale_world expected_revision=7 with gate off | $(date -Is) | EXPECT: error_code=STALE_WORLD execution_started=false ==="
    timeout 30 python3 "$C" --pose 0.20 0.05 0.20 0 0 0 1 --expected-revision 7 --request-id case6_stale_world
    echo "RC=$?"
  } 2>&1 | tee "$E/06_stale_world.out"
  gate_check stale_world_code "$E/06_stale_world.out" '"error_code": "ERR_STALE_WORLD"'
}

case_ik_unreachable() {
  { echo "=== case7 ik_unreachable target=(0.42,0,0.10) inside box beyond reach | $(date -Is) | EXPECT: error_code=IK_UNREACHABLE execution_started=false fast-fail~1s ==="
    timeout 60 python3 "$C" --pose 0.42 0.0 0.10 0 0 0 1 --request-id case7_ik_unreachable
    echo "RC=$?"
  } 2>&1 | tee "$E/07_ik_unreachable.out"
  gate_check ik_unreachable_code "$E/07_ik_unreachable.out" '"error_code": "ERR_IK_UNREACHABLE"'
}

case_timeout() {
  { echo "=== case8 timeout deadline=800ms on far target (0.25,0.15,0.15) | $(date -Is) | EXPECT: error_code=EXECUTION_TIMEOUT preempted=true stop_confirmed=true ==="
    timeout 90 python3 "$C" --pose 0.25 0.15 0.15 0 0 0 1 --deadline 800 --request-id case8_timeout
    echo "RC=$?"
  } 2>&1 | tee "$E/08_timeout.out"
  gate_check timeout_code "$E/08_timeout.out" '"error_code": "ERR_EXECUTION_TIMEOUT"'
  gate_check timeout_preempted "$E/08_timeout.out" 'preempted; stop confirmed'
}

case_cancel() {
  { echo "=== case9 cancel 1.0s into EXECUTING, target=(0.05,-0.28,0.18) | $(date -Is) | EXPECT: outcome=CANCELED preempted=true stop_confirmed=true ==="
    timeout 90 python3 "$C" --pose 0.05 -0.28 0.18 0 0 0 1 --cancel-after-executing 1.0 --request-id case9_cancel
    echo "RC=$?"
  } 2>&1 | tee "$E/09_cancel.out"
  gate_check cancel_outcome "$E/09_cancel.out" '"outcome": "OUTCOME_CANCELED"'
  gate_check cancel_stop_confirmed "$E/09_cancel.out" 'preempted; stop confirmed'
}

case_regression() {
  { echo "=== case10 day1_regression plan_execute.py 0.0 -0.9 0.9 0.5 | $(date -Is) | EXPECT: PLAN/EXECUTE error_code=1 MOTION_DETECTED=True (arm OFF the all-zero home) ==="
    timeout 120 python3 "$P" 0.0 -0.9 0.9 0.5
    echo "RC=$?"
  } 2>&1 | tee "$E/10_day1_regression.out"
  # audit P1-5: MOTION_DETECTED=False used to print and still exit 0 - the
  # grep existed but nothing consumed it.  Now the battery goes red.
  gate_check regression_motion "$E/10_day1_regression.out" 'MOTION_DETECTED=True'
}

if [ $# -eq 0 ]; then
  echo "usage: 32_day2_acceptance.sh <case> [<case> ...]" >&2
  echo "cases: happy_a happy_b invalid_workspace invalid_quat invalid_profile stale_world ik_unreachable timeout cancel regression" >&2
  exit 2
fi

for c in "$@"; do
  "case_$c"
done
gate_finalize
exit $GATE_FAILS
