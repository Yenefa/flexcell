#!/usr/bin/env bash
# Week-1 evidence archive: copy skill JSONL logs + build summary (run in WSL as ros)
E=/mnt/f/flexcell-stage/setup/acceptance/week1
for f in observe pick place verify task_fsm carry; do
  cp "/home/ros/.ros/flexcell/$f.jsonl" "$E/$f.jsonl" 2>/dev/null
done
{
  echo "=== Week-1 acceptance summary | $(date -Is) ==="
  echo "stack: flexcell_world.sdf (pre-placed target_box) | carry: teleport servo (set_pose @10Hz)"
  echo "battery: F:/flexcell-stage/setup/47_w1_acceptance.sh | upstream HEAD a6b00e7 + flexcell Week-1 local"
  echo
  grep -H -E "\"outcome\"|\"error_code\"|\"detail\"|RC=|object_at_place|final_position_error" \
    "$E/w1_1_observe.out" "$E/w1_2_task_happy.out" "$E/w1_3_verify_post.out" \
    "$E/w1_4_pick_unknown.out" "$E/w1_5_place_not_carried.out" "$E/w1_6_busy.out" \
    "$E/w1_7_place_unreachable.out" 2>/dev/null | sed 's|/mnt/f/flexcell-stage/setup/acceptance/week1/||g' | cut -c1-200
  echo
  echo "--- notes ---"
  echo "w1_5: battery run hit a one-off client-side hang (RC=124); manual rerun returned NOT_CARRIED in 39ms (verified)."
  echo "w1_6: first task SUCCEEDED (err 6.5mm), second correctly rejected RESOURCE_BUSY."
  echo "w1_7: unreachable place propagated as typed failure; box honestly left carried; cleaned by final restart."
  echo
  echo "--- Day-2 regression (32 battery, same session) ---"
  grep -H -E "\"outcome\"|\"error_code\"|MOTION_DETECTED|PLAN error|EXECUTE error" \
    /mnt/f/flexcell-stage/setup/acceptance/day2/01_happy_a.out /mnt/f/flexcell-stage/setup/acceptance/day2/02_happy_b.out \
    /mnt/f/flexcell-stage/setup/acceptance/day2/03_invalid_workspace.out /mnt/f/flexcell-stage/setup/acceptance/day2/04_invalid_quat.out \
    /mnt/f/flexcell-stage/setup/acceptance/day2/05_invalid_profile.out /mnt/f/flexcell-stage/setup/acceptance/day2/06_stale_world.out \
    /mnt/f/flexcell-stage/setup/acceptance/day2/07_ik_unreachable.out /mnt/f/flexcell-stage/setup/acceptance/day2/08_timeout.out \
    /mnt/f/flexcell-stage/setup/acceptance/day2/09_cancel.out /mnt/f/flexcell-stage/setup/acceptance/day2/10_day1_regression.out \
    2>/dev/null | sed 's|/mnt/f/flexcell-stage/setup/acceptance/day2/||g' | cut -c1-160
} > "$E/12_summary.out" 2>&1
echo "archived:"
ls "$E"
