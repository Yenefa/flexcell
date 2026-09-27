#!/usr/bin/env bash
# Day-2 evidence archive: copy structured JSONL log + build summary (run inside WSL as ros)
E=/mnt/f/flexcell-stage/setup/acceptance/day2
cp /home/ros/.ros/flexcell/move_to_pose.jsonl "$E/move_to_pose.jsonl"
{
  echo "=== Day-2 MoveToPose acceptance summary | $(date -Is) ==="
  echo "battery: F:/flexcell-stage/setup/32_day2_acceptance.sh | upstream HEAD a6b00e7 | server: flexcell_skills move_to_pose.launch.py"
  echo
  for f in "$E"/00_*.out "$E"/01_*.out "$E"/02_*.out "$E"/03_*.out "$E"/04_*.out "$E"/05_*.out "$E"/06_*.out "$E"/07_*.out "$E"/08_*.out "$E"/09_*.out "$E"/10_*.out; do
    n=$(basename "$f")
    o=$(grep -o '"outcome": "[A-Z_]*"' "$f" | head -1 | cut -d'"' -f4)
    e=$(grep -o '"error_code": "[A-Z_]*"' "$f" | head -1 | cut -d'"' -f4)
    p=$(grep -o '"position_error_m": [0-9.]*' "$f" | head -1)
    d=$(grep -o '"detail": "[^"]*"' "$f" | head -1 | cut -d'"' -f4 | cut -c1-90)
    echo "$n | outcome=${o:-<n/a>} error_code=${e:-} ${p:-} detail=${d:-}"
  done
  echo
  echo "--- plan_execute regression lines ---"
  grep -E "PLAN error_code|EXECUTE error_code|MOTION_DETECTED" "$E"/10_day1_regression.out
  echo
  echo "--- server alive check ---"
  pgrep -af move_to_pose_server | grep -v bash || echo "SERVER DEAD"
  echo
  echo "--- server log tail ---"
  tail -5 "$E/move_to_pose_server.log"
} > "$E/11_summary.out" 2>&1
echo "archive done:"
ls -la "$E"
