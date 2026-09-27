#!/usr/bin/env bash
# Week-1.5 acceptance battery:
#   A happy path | B recovery (injected, once) | C retry exhausted (always)
#   D invalid target | E reset after success/failure | F 5-run repeatability
# Usage: bash 61_w15_acceptance.sh happy|recovery|exhaust|invalid|reset|repeat|regress
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
CLI=/tmp/flexcell_cli
C=src/flexcell/flexcell_skills/test/w1_client.py
E=/mnt/f/flexcell-stage/setup/acceptance/week15
mkdir -p "$E"

run_demo() { # <name> <scenario>
  local name="$1" scen="$2"
  {
    echo "=== ${name} | $(date -Is) | scenario=${scen} ==="
    timeout 170 python3 "$C" --action demo --scenario "$scen"
    echo "RC=$?"
  } 2>&1 | tee "$E/${name}.out"
}

reset_run() { # <name>
  {
    echo "=== ${1} | $(date -Is) ==="
    bash "$CLI" reset
    echo "RC=$?"
  } 2>&1 | tee "$E/${1}.out" | grep -E '"ok"|canonical|scene_cleared|arm_home"|carry_dis'
}

case_happy() {
  reset_run 61_E0_reset_before
  run_demo 61_A_happy week1_demo_v1
  grep -E '"outcome"|object_a_at_zone|object_b_at_zone|zone_a_error_m|zone_b_error_m|run_id' \
    "$E/61_A_happy.out" | head -6
}

case_recovery() {
  reset_run 61_E1_reset_after_success
  python3 "$C" --action inject --inject "recovery_demo_v1:once"
  run_demo 61_B_recovery recovery_demo_v1
  grep -E '"outcome"|ERR_RECOVERY|fsm_trace|PICK_B|RECOVERY|run_id' \
    "$E/61_B_recovery.out" | head -12
}

case_exhaust() {
  reset_run 61_E2_reset_before_exhaust
  python3 "$C" --action inject --inject "exhaust_demo_v1:always"
  run_demo 61_C_exhausted exhaust_demo_v1
  grep -E '"outcome"|error_code|fsm_trace|PICK_B|RECOVERY' \
    "$E/61_C_exhausted.out" | head -12
  reset_run 61_E3_reset_after_failure
}

case_invalid() {
  python3 "$C" --action inject --inject ""
  {
    echo "=== 61_D_invalid | $(date -Is) | EXPECT: typed failure (IK unreachable) ==="
    timeout 120 python3 "$C" --action task --object target_box_a --pose 0.42 0 0.0175
    echo "RC=$?"
  } 2>&1 | tee "$E/61_D_invalid.out"
  grep -E '"outcome"|"error_code"|"detail"' "$E/61_D_invalid.out" | head -3
}

case_repeat() {
  python3 "$C" --action inject --inject ""
  : > "$E/61_F_repeat_summary.out"
  for i in 1 2 3 4 5; do
    bash "$CLI" reset > /dev/null 2>&1
    timeout 170 python3 "$C" --action demo --scenario "repeat_run_$i" \
      > "/tmp/61_F_run_$i.out" 2>&1
    rc=$?
    o=$(grep -o '"outcome": "[A-Z_]*"' "/tmp/61_F_run_$i.out" | head -1 | cut -d'"' -f4)
    d=$(grep -o '"wall_seconds": [0-9.]*' "/tmp/61_F_run_$i.out" | head -1 | cut -d' ' -f2)
    ea=$(grep -o '"zone_a_error_m": [0-9.]*' "/tmp/61_F_run_$i.out" | head -1 | grep -o '[0-9.]*$')
    eb=$(grep -o '"zone_b_error_m": [0-9.]*' "/tmp/61_F_run_$i.out" | head -1 | grep -o '[0-9.]*$')
    echo "run $i | outcome=$o duration=${d}s zone_a_err=${ea}m zone_b_err=${eb}m" \
      | tee -a "$E/61_F_repeat_summary.out"
    cp "/tmp/61_F_run_$i.out" "$E/61_F_run_$i.out"
  done
  echo "--- duplicate server check ---"
  for s in observe_server pick_server place_server verify_server task_fsm_server carry_server move_to_pose_server; do
    echo "$s: $(pgrep -c -f "flexcell_skills/$s")"
  done | tee -a "$E/61_F_repeat_summary.out"
  echo "success count: $(grep -c 'outcome=OUTCOME_SUCCEEDED' "$E/61_F_repeat_summary.out")" \
    | tee -a "$E/61_F_repeat_summary.out"
}

case "$1" in
  happy) case_happy ;;
  recovery) case_recovery ;;
  exhaust) case_exhaust ;;
  invalid) case_invalid ;;
  reset) reset_run 61_E_reset_manual ;;
  repeat) case_repeat ;;
  regress) bash /tmp/d2.sh happy_a happy_b invalid_workspace invalid_quat invalid_profile stale_world ik_unreachable timeout cancel regression ;;
  *) echo "usage: 61_w15_acceptance.sh happy|recovery|exhaust|invalid|reset|repeat|regress"; exit 2 ;;
esac
