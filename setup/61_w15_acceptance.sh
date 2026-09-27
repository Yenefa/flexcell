#!/usr/bin/env bash
# Week-1.5 acceptance battery:
#   A happy path | B recovery (injected, once) | C retry exhausted (always)
#   D invalid target | E reset after success/failure | F 5-run repeatability
# Usage: bash 61_w15_acceptance.sh happy|recovery|exhaust|invalid|reset|repeat|all
#
# Audit P1-5: every case now ends in a HARD GATE (gate_check) and the battery
# exits non-zero when any gate failed - "echo EXPECT and move on" is gone.
# Audit P1-7: artifacts land in a versioned session dir, never overwritten.
# Audit P1-8: reset artifacts are gated on the gz.msgs.Pose traceback flood.
#
# Machine overrides: FLEXCELL_WS / FLEXCELL_STAGE (see lib_gate.sh).
source "$(dirname "$0")/lib_gate.sh"
source /opt/ros/jazzy/setup.bash
source "$(_flexcell_ws)/install/setup.bash"
cd "$(_flexcell_ws)"
CLI=${FLEXCELL_CLI:-/tmp/flexcell_cli}
C=src/flexcell/flexcell_skills/test/w1_client.py
GATE_INIT_DONE=0
ensure_session() {
  if [ "$GATE_INIT_DONE" -eq 0 ]; then
    gate_init week15_battery
    E="$GATE_SESSION"
    export E
    GATE_INIT_DONE=1
  fi
}
E=""
ensure_session

run_demo() { # <name> <scenario>
  local name="$1" scen="$2"
  {
    echo "=== ${name} | $(date -Is) | scenario=${scen} ==="
    timeout 170 python3 "$C" --action demo --scenario "$scen"
    echo "RC=$?"
  } 2>&1 | tee "$E/${name}.out"
}

do_reset() { # <name>
  # New-machine flow uses the lifecycle CLI; on machines without it (or when
  # FLEXCELL_CLI is unset) fall back to the in-repo admin reset.
  if [ -n "${FLEXCELL_CLI:-}" ] && [ -x "$FLEXCELL_CLI" ]; then
    bash "$FLEXCELL_CLI" reset
  else
    FLEXCELL_WS="$(_flexcell_ws)" timeout 240 python3 setup/flexcell_admin.py reset
  fi
}

reset_run() { # <name>
  {
    echo "=== ${1} | $(date -Is) ==="
    do_reset
    echo "RC=$?"
  } 2>&1 | tee "$E/${1}.out" | grep -E '"ok"|canonical|scene_cleared|arm_home"|carry_dis' || true
}

case_happy() {
  ensure_session
  reset_run 61_E0_reset_before
  gate_flood "$E/61_E0_reset_before.out"
  run_demo 61_A_happy week1_demo_v1
  gate_check happy_outcome "$E/61_A_happy.out" '"outcome": "OUTCOME_SUCCEEDED"'
  gate_check happy_zone_a "$E/61_A_happy.out" '"object_a_at_zone": true'
  gate_check happy_zone_b "$E/61_A_happy.out" '"object_b_at_zone": true'
  grep -E '"outcome"|object_a_at_zone|object_b_at_zone|zone_a_error_m|zone_b_error_m|run_id' \
    "$E/61_A_happy.out" | head -6
}

case_recovery() {
  ensure_session
  reset_run 61_E1_reset_after_success
  gate_flood "$E/61_E1_reset_after_success.out"
  python3 "$C" --action inject --inject "recovery_demo_v1:once"
  run_demo 61_B_recovery recovery_demo_v1
  gate_check recovery_outcome "$E/61_B_recovery.out" '"outcome": "OUTCOME_SUCCEEDED"'
  gate_check recovery_trace "$E/61_B_recovery.out" 'REOBSERVE|RECOVERY|RECOVER'
  grep -E '"outcome"|ERR_RECOVERY|fsm_trace|PICK_B|RECOVERY|run_id' \
    "$E/61_B_recovery.out" | head -12
}

case_exhaust() {
  ensure_session
  reset_run 61_E2_reset_before_exhaust
  gate_flood "$E/61_E2_reset_before_exhaust.out"
  python3 "$C" --action inject --inject "exhaust_demo_v1:always"
  run_demo 61_C_exhausted exhaust_demo_v1
  # audit P1-2 acceptance: the exhausted retry budget must come back TYPED
  # (ERR_RECOVERY_EXHAUSTED), not ERR_SKILL_FAILED + "policy state error"
  gate_check exhaust_outcome "$E/61_C_exhausted.out" '"outcome": "OUTCOME_FAILED"'
  gate_check exhaust_typed "$E/61_C_exhausted.out" '"error_code": "ERR_RECOVERY_EXHAUSTED"'
  if grep -q 'policy state error' "$E/61_C_exhausted.out"; then
    echo "GATE FAIL exhaust_typed: catch-all 'policy state error' resurfaced"
    GATE_FAILS=$((GATE_FAILS + 1))
  fi
  grep -E '"outcome"|error_code|fsm_trace|PICK_B|RECOVERY' \
    "$E/61_C_exhausted.out" | head -12
  reset_run 61_E3_reset_after_failure
  gate_flood "$E/61_E3_reset_after_failure.out"
}

case_invalid() {
  ensure_session
  python3 "$C" --action inject --inject ""
  {
    echo "=== 61_D_invalid | $(date -Is) | EXPECT: typed failure (IK unreachable) ==="
    timeout 120 python3 "$C" --action task --object target_box_a --pose 0.42 0 0.0175
    echo "RC=$?"
  } 2>&1 | tee "$E/61_D_invalid.out"
  # The negative path must be TYPED.  Two honest shapes exist: the task's
  # place pose (0.42,0,...) is beyond reach -> ERR_IK_UNREACHABLE on the
  # place leg; or the preceding pick flakes first (magnetic carry, the
  # known single-point dependency) -> the pick's typed error propagates.
  # Both are typed negatives; a ghost success or the catch-all
  # 'policy state error' wording is what this gate exists to catch.
  gate_check invalid_failed "$E/61_D_invalid.out" '"outcome": "OUTCOME_FAILED"'
  gate_check invalid_typed "$E/61_D_invalid.out" \
    'ERR_(IK_UNREACHABLE|GRASP_FAILED|PLACE_FAILED|MOTION_FAILED)'
  if grep -q 'policy state error' "$E/61_D_invalid.out"; then
    echo "GATE FAIL invalid_typed: catch-all 'policy state error' resurfaced"
    GATE_FAILS=$((GATE_FAILS + 1))
  fi
  grep -E '"outcome"|"error_code"|"detail"' "$E/61_D_invalid.out" | head -3
}

case_repeat() {
  ensure_session
  python3 "$C" --action inject --inject ""
  : > "$E/61_F_repeat_summary.out"
  for i in 1 2 3 4 5; do
    do_reset > /dev/null 2>&1
    timeout 170 python3 "$C" --action demo --scenario "repeat_run_$i" \
      > "$E/61_F_run_$i.out" 2>&1
    rc=$?
    o=$(grep -o '"outcome": "[A-Z_]*"' "$E/61_F_run_$i.out" | head -1 | cut -d'"' -f4)
    d=$(grep -o '"wall_seconds": [0-9.]*' "$E/61_F_run_$i.out" | head -1 | cut -d' ' -f2)
    ea=$(grep -o '"zone_a_error_m": [0-9.]*' "$E/61_F_run_$i.out" | head -1 | grep -o '[0-9.]*$')
    eb=$(grep -o '"zone_b_error_m": [0-9.]*' "$E/61_F_run_$i.out" | head -1 | grep -o '[0-9.]*$')
    echo "run $i | outcome=$o duration=${d}s zone_a_err=${ea}m zone_b_err=${eb}m" \
      | tee -a "$E/61_F_repeat_summary.out"
  done
  echo "--- duplicate server check ---"
  for s in observe_server pick_server place_server verify_server task_fsm_server carry_server move_to_pose_server; do
    echo "$s: $(pgrep -c -f "flexcell_skills/$s")"
  done | tee -a "$E/61_F_repeat_summary.out"
  echo "success count: $(grep -c 'outcome=OUTCOME_SUCCEEDED' "$E/61_F_repeat_summary.out")" \
    | tee -a "$E/61_F_repeat_summary.out"
  # audit P1-5: repeatability is gated - 5/5 or the battery is red
  gate_check repeat_5_of_5 "$E/61_F_repeat_summary.out" 'success count: 5'
}

GATE_FINISHED=0
finish() {
  [ "$GATE_FINISHED" -eq 0 ] && { GATE_FINISHED=1; gate_finalize; }
}

case "$1" in
  happy) case_happy ; finish ;;
  recovery) case_recovery ; finish ;;
  exhaust) case_exhaust ; finish ;;
  invalid) case_invalid ; finish ;;
  reset) ensure_session ; reset_run 61_E_reset_manual ; gate_flood "$E/61_E_reset_manual.out" ; finish ;;
  repeat) case_repeat ; finish ;;
  all)
    case_happy
    case_recovery
    case_exhaust
    case_invalid
    finish
    ;;
  *) echo "usage: 61_w15_acceptance.sh happy|recovery|exhaust|invalid|reset|repeat|all"; exit 2 ;;
esac
[ "$GATE_FINISHED" -eq 0 ] && finish
exit $GATE_FAILS
