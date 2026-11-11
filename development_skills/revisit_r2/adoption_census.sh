#!/usr/bin/env bash
# M3 -- adoption census. How many round-2 drivers/evidence files reference each entrypoint?
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
ACC="$WT/setup/acceptance"
R2="$ACC/evobot_t08_first_push_20261112 $ACC/evobot_t08_trajectory_verifier_20261112 \
    $ACC/evobot_t08_saturation_diagnosis_20261112 $ACC/evobot_p0_paired_20261112 \
    $ACC/evobot_gripper_false_negative_measured_20261112 $ACC/evobot_push_recover_20261112"
echo "entrypoint                 round-2 references"
for s in preflight.py safe_pattern.py call_path_check.py effect_check.py check_ros_interfaces.py; do
  n=$(grep -rl "$s" $R2 2>/dev/null | wc -l)
  printf '  %-26s %s\n' "$s" "$n"
done
echo
echo "NOTE: check_ros_interfaces.py was authored at 81e530a9 (01:46);"
echo "      the four skills at 5866de4b (02:10). The tool predates the skills."
echo
echo "interface_check.log archived anywhere in the repo:"
find "$WT" -name interface_check.log 2>/dev/null | wc -l
