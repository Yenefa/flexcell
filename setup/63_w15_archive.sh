#!/usr/bin/env bash
E=/mnt/f/flexcell-stage/setup/acceptance/week15
for f in demo_runs observe pick place verify carry task_fsm; do
  cp "/home/ros/.ros/flexcell/$f.jsonl" "$E/" 2>/dev/null
done
{
  echo "=== Week-1.5 acceptance summary | $(date -Is) | scenario=week1_demo_v1 ==="
  echo "lifecycle: flexcell start/stop/reset (PID-group ownership + strict health gate)"
  echo
  grep -H -E "outcome|zone_a_err|zone_b_err|success count|PICK_B|RECOVERY|error_code" \
    "$E/61_A_happy.out" "$E/61_B_recovery.out" "$E/61_C_exhausted.out" \
    "$E/61_D_invalid.out" "$E/61_F_repeat_summary.out" 2>/dev/null \
    | sed "s|$E/||g" | cut -c1-150
  echo
  echo "Day-2 regression: 10/10 (outputs refreshed under ../day2/)"
} > "$E/61_summary.out" 2>&1
echo "files: $(ls "$E" | wc -l)"
tail -4 "$E/61_F_repeat_summary.out"
