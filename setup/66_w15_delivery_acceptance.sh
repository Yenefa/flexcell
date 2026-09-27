#!/usr/bin/env bash
# 66_w15_delivery_acceptance.sh — Week-1.5 cold-start DELIVERY acceptance
# Delivery acceptance only: cold boot -> start -> reset -> happy demo ->
# recovery demo -> reset -> clean stop. No code changes, no new features.
# Usage: tr -d "\r" < 66_w15_delivery_acceptance.sh > /tmp/dlv66 && bash /tmp/dlv66 <phase>
# Phases: precheck|start|reset1|demo|recovery|reset2|stop|poststop
# Note: reset 判据看 JSON "ok"，RC 仅参考（139=退出竞态，踩坑日记 B 级 2026-09-26）。
set -o pipefail

E=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
CLI=/tmp/flexcell_cli
WS=/home/ros/agentic_workcell_ws
CLIENT=src/flexcell/flexcell_skills/test/w1_client.py
J=/home/ros/.ros/flexcell
mkdir -p "$E"

cap() { # cap <file> <label> <cmd...> — transcript to file, one-line digest to stdout
  local out="$E/$1" label="$2"; shift 2
  { echo "=== ${label} | $(date -Is) ==="; "$@"; echo "RC=$?"; } > "$out" 2>&1
  echo "[cap] ${label} ($(grep -o 'RC=[0-9]*' "$out" | tail -1))"
}

env_ros() {
  source /opt/ros/jazzy/setup.bash
  source "$WS/install/setup.bash"
  cd "$WS" || exit 3
}

scan() { # scan <name> — residual process scan; returns count of patterns with hits
  local f="$E/$1.out"
  {
    echo "=== residual scan | $(date -Is) ==="
    echo "boot_since: $(uptime -s) (up $(uptime -p))"
    echo "uptime_s: $(cut -d' ' -f1 /proc/uptime)"
    echo "pids_dir: $(ls -d /tmp/flexcell_lifecycle 2>/dev/null || echo ABSENT)"
    echo "cli_tmp: $(ls /tmp/flexcell_cli 2>/dev/null || echo ABSENT)"
    local total=0
    scan_one() {
      local name="$1" pat="$2" n
      n=$(pgrep -c -f "$pat" 2>/dev/null || true)
      echo "${name}: ${n}"
      if [ "${n}" -gt 0 ]; then pgrep -af "$pat" 2>/dev/null | head -5; total=$((total+1)); fi
    }
    scan_one gz_server 'gz si[m]'
    scan_one gazebo 'gazeb[o]'
    scan_one move_group 'move_grou[p]'
    scan_one robot_state_publisher 'robot_state_publishe[r]'
    scan_one ros2_control_node 'ros2_control_nod[e]'
    scan_one controller_spawner 'spawne[r]'
    scan_one skill_servers 'observe_serve[r]|pick_serve[r]|place_serve[r]|verify_serve[r]|task_fsm_serve[r]|carry_serve[r]|move_to_pose_serve[r]'
    scan_one ros2_launch 'ros2 launc[h]'
    scan_one launch_py 'launch\.p[y]'
    scan_one rviz2 'rviz[2]'
    scan_one flexcell_admin 'flexcell_admi[n]'
    scan_one ros2_daemon '_ros2_daemo[n]'
    echo "patterns_with_hits: ${total}"
  } > "$f" 2>&1
  local hits
  hits=$(grep -o 'patterns_with_hits: [0-9]*' "$f" | grep -o '[0-9]*$')
  echo "[scan] $1: patterns_with_hits=${hits}"
  return "${hits}"
}

reset_digest() { # reset_digest <file> — pull the JSON report fields from a noisy transcript
  grep -oE '"[a-zA-Z_]+": ?[^,{}]*' "$E/$1" | tail -30
}

do_reset() { # do_reset <file>
  cap "$1" "flexcell reset" bash "$CLI" reset
  echo "--- reset JSON digest (tail) ---"
  reset_digest "$1"
  grep -q '"ok": true' "$E/$1"
}

phase_precheck() {
  scan 66_pre_start
}

phase_start() {
  tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"
  { echo "=== flexcell start | $(date -Is) ==="
    t0=$(date +%s); bash "$CLI" start; rc=$?; t1=$(date +%s)
    echo "START_DURATION_S=$((t1-t0))"; echo "RC=$rc"; } > "$E/66_start.out" 2>&1
  echo "[cap] start rc=$rc dur=$((t1-t0))s"
  cap 66_status_after_start.out "flexcell status" bash "$CLI" status
  cap 66_health_strict.out "flexcell health (strict)" bash "$CLI" health
  { echo "=== server process counts (expect 1 each) | $(date -Is) ==="
    for s in observe_server pick_server place_server verify_server task_fsm_server carry_server move_to_pose_server; do
      echo "$s: $(pgrep -c -f "flexcell_skills/$s")"
    done
    echo "move_group: $(pgrep -c -f 'move_grou[p]')"
    echo "gz_server: $(pgrep -c -f 'gz si[m]')"
    echo "robot_state_publisher: $(pgrep -c -f 'robot_state_publishe[r]')"
  } > "$E/66_server_counts.out" 2>&1
  cat "$E/66_server_counts.out"
  echo "--- start.out tail ---"
  tail -n 20 "$E/66_start.out"
  grep -q '^START OK' "$E/66_start.out"
}

phase_reset1() { do_reset 66_reset1.out; }

phase_demo() {
  env_ros
  cap 66_demo_happy.out "happy demo week1_demo_v1" timeout 170 python3 "$CLIENT" --action demo --scenario week1_demo_v1
  grep -E '"outcome"|object_a_at_zone|object_b_at_zone|zone_a_error_m|zone_b_error_m|run_id|wall_seconds|"duration_s"' \
    "$E/66_demo_happy.out" | head -12 | tee "$E/66_demo_happy_key.out"
  tail -n 1 "$J/demo_runs.jsonl" > "$E/66_run_record_happy.jsonl"
  {
    echo "=== WorldState / revisions extraction | $(date -Is) ==="
    echo "--- last observe.jsonl line keys ---"
    tail -n 1 "$J/observe.jsonl" | grep -oE '"[a-zA-Z_]+":' | head -40
    echo "--- revision-like fields (observe.jsonl, tail) ---"
    grep -oE '"[a-z_]*revis[a-z_]*": ?[0-9]+' "$J/observe.jsonl" | tail -8
    echo "--- last task_fsm.jsonl line keys ---"
    tail -n 1 "$J/task_fsm.jsonl" | grep -oE '"[a-zA-Z_]+":' | head -40
    echo "--- revision-like fields (task_fsm.jsonl, tail) ---"
    grep -oE '"[a-z_]*revis[a-z_]*": ?[0-9]+' "$J/task_fsm.jsonl" | tail -8
  } > "$E/66_worldstate.out" 2>&1
  cat "$E/66_worldstate.out"
  grep -q '"outcome": "OUTCOME_SUCCEEDED"' "$E/66_demo_happy.out"
}

phase_recovery() {
  env_ros
  do_reset 66_reset_pre_recovery.out || return $?
  cap 66_inject_once.out "inject recovery_demo_v1:once" python3 "$CLIENT" --action inject --inject "recovery_demo_v1:once"
  cap 66_demo_recovery.out "recovery demo recovery_demo_v1" timeout 170 python3 "$CLIENT" --action demo --scenario recovery_demo_v1
  grep -E '"outcome"|fsm_trace|PICK_B|RECOVERY|REOBSERVE|RETRY|run_id|"error_code"' \
    "$E/66_demo_recovery.out" | head -24 | tee "$E/66_demo_recovery_key.out"
  tail -n 1 "$J/demo_runs.jsonl" > "$E/66_run_record_recovery.jsonl"
  cap 66_inject_clear.out "inject clear" python3 "$CLIENT" --action inject --inject ""
  grep -q '"outcome": "OUTCOME_SUCCEEDED"' "$E/66_demo_recovery.out" \
    && grep -qE 'REOBSERVE|attempt=2|RECOVER' "$E/66_demo_recovery.out"
}

phase_reset2() { do_reset 66_reset_post_recovery.out; }

phase_stop() {
  cap 66_stop.out "flexcell stop" bash "$CLI" stop
  echo "--- stop.out tail ---"
  tail -n 15 "$E/66_stop.out"
  if grep -q 'STOP INCOMPLETE' "$E/66_stop.out"; then return 1; fi
  local rc
  rc=$(grep -o 'RC=[0-9]*' "$E/66_stop.out" | tail -1 | grep -o '[0-9]*$')
  [ "$rc" = "0" ]
}

phase_poststop() {
  scan 66_post_stop
}

case "$1" in
  precheck) phase_precheck ;;
  start) phase_start ;;
  reset1) phase_reset1 ;;
  demo) phase_demo ;;
  recovery) phase_recovery ;;
  reset2) phase_reset2 ;;
  stop) phase_stop ;;
  poststop) phase_poststop ;;
  *) echo "usage: 66_w15_delivery_acceptance.sh precheck|start|reset1|demo|recovery|reset2|stop|poststop"; exit 2 ;;
esac
