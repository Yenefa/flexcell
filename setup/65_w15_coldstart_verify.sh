#!/usr/bin/env bash
# 65_w15_coldstart_verify.sh — project-033-flexcell Week-1.5 cold-start verification
# Purpose: after `wsl --terminate Ubuntu-24.04`, bring the stack up from zero using
#          ONLY flexcell start/reset, run one happy demo (scenario week1_demo_v1),
#          reset, and leave health + demo evidence under acceptance/week15/cs_20260926/.
# Usage (WSL, user ros):
#   tr -d "\r" < /mnt/f/flexcell-stage/setup/65_w15_coldstart_verify.sh > /tmp/cs.sh
#   bash /tmp/cs.sh start
#   bash /tmp/cs.sh demo
# NOTE: no `set -u` — it breaks ROS setup.bash (diary B 2026-09-26).
set -o pipefail

E=/mnt/f/flexcell-stage/setup/acceptance/week15/cs_20260926
CLI=/tmp/flexcell_cli
WS=/home/ros/agentic_workcell_ws
CLIENT=src/flexcell/flexcell_skills/test/w1_client.py
J=/home/ros/.ros/flexcell
mkdir -p "$E"

run_cap() { # run_cap <outfile> <label> <cmd...> — full transcript to file, one-line digest to stdout
  local out="$E/$1" label="$2"; shift 2
  { echo "=== ${label} | $(date -Is) ==="; "$@"; echo "RC=$?"; } > "$out" 2>&1
  echo "[cap] ${label} done ($(grep -o 'RC=[0-9]*' "$out" | tail -1))"
}

phase_start() {
  tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"
  run_cap cs_start.out "flexcell start" bash "$CLI" start
  run_cap cs_status_after_start.out "flexcell status" bash "$CLI" status
  run_cap cs_health_strict.out "flexcell health strict" bash "$CLI" health
  echo "--- cs_start.out tail ---"
  tail -n 25 "$E/cs_start.out"
  echo "--- cs_status_after_start.out ---"
  head -n 45 "$E/cs_status_after_start.out"
}

phase_demo() {
  source /opt/ros/jazzy/setup.bash
  source "$WS/install/setup.bash"
  cd "$WS" || exit 3
  run_cap cs_reset_before.out "reset before demo" bash "$CLI" reset
  run_cap cs_A_happy.out "happy demo week1_demo_v1" timeout 170 python3 "$CLIENT" --action demo --scenario week1_demo_v1
  grep -E '"outcome"|object_a_at_zone|object_b_at_zone|zone_a_error_m|zone_b_error_m|run_id|evidence_id' \
    "$E/cs_A_happy.out" | head -10 | tee "$E/cs_A_happy_key.out"
  run_cap cs_reset_after.out "reset after demo" bash "$CLI" reset
  run_cap cs_status_after_reset.out "flexcell status" bash "$CLI" status
  for f in demo_runs observe pick place verify carry task_fsm; do
    if [ -f "$J/$f.jsonl" ]; then cp "$J/$f.jsonl" "$E/$f.jsonl"; else echo "MISS $f.jsonl" >> "$E/cs_copy.log"; fi
  done
  tail -n 1 "$E/demo_runs.jsonl" > "$E/cs_run_record.jsonl"
  {
    echo "coldstart verify done $(date -Is)"
    echo "evidence dir: $E"
    ls -la "$E" | tail -n +2
  } > "$E/cs_copy.log"
  cat "$E/cs_copy.log"
}

case "$1" in
  start) phase_start ;;
  demo) phase_demo ;;
  *) echo "usage: 65_w15_coldstart_verify.sh start|demo"; exit 2 ;;
esac
