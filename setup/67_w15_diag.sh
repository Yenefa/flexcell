#!/usr/bin/env bash
# 67_w15_diag.sh — delivery acceptance diagnostics (read-only)
# Scans lifecycle launch logs for carry servo failures and vendor transport
# crash loops; pulls pick attempt history around the failed legs.
set -o pipefail

E=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
L=/tmp/flexcell_lifecycle/logs
J=/home/ros/.ros/flexcell

{
  echo "=== lifecycle log scan | $(date -Is) ==="
  for f in "$L"/*.log; do
    echo "--- $(basename "$f") ---"
    echo "set_pose_failed=$(grep -c 'set_pose failed' "$f")"
    echo "unregistered_TypeError=$(grep -c 'No message class registered' "$f")"
    echo "carry_ENGAGED=$(grep -c 'carry ENGAGED' "$f")"
    echo "carry_RELEASED=$(grep -c 'carry RELEASED' "$f")"
    echo "log_bytes=$(wc -c < "$f")"
  done
  echo
  echo "=== fleet.log: set_pose failed warns (last 15) ==="
  grep -n 'set_pose failed' "$L/fleet.log" | tail -15
  echo
  echo "=== fleet.log: unregistered TypeError first+last occurrence ==="
  grep -n 'No message class registered' "$L/fleet.log" | sed -n '1p;$p'
  echo
  echo "=== fleet.log: carry ENGAGED/RELEASED timeline (all) ==="
  grep -nE 'carry ENGAGED|carry RELEASED' "$L/fleet.log"
  echo
  echo "=== pick.jsonl: 6 records from end (attempt history) ==="
  tail -n 6 "$J/pick.jsonl"
} > "$E/67_diag.out" 2>&1

wc -l "$E/67_diag.out"
tail -n 25 "$E/67_diag.out"
