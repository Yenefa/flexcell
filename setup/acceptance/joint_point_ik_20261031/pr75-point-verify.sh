#!/usr/bin/env bash
set -eo pipefail
cd /home/ros/agentic_workcell_ws
git diff --quiet
git fetch --no-tags /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone refs/heads/fix/joint-point-ik
git merge --ff-only FETCH_HEAD
source /opt/ros/jazzy/setup.bash
source install/pr75-locked-upstream/setup.bash
source install/pr75/local_setup.bash
export CMAKE_BUILD_PARALLEL_LEVEL=2 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PYTHONDONTWRITEBYTECODE=1
FC_OUT=/home/ros/agentic_workcell_ws/artifacts/joint-point-fix-20261031/verification-v2
mkdir "$FC_OUT"
colcon --log-base log/joint-point-all-build build --merge-install --build-base build/pr75 --install-base install/pr75 \
  --packages-select flexcell_interfaces flexcell_skills flexcell_gazebo flexcell_mtc --parallel-workers 2 \
  --cmake-args -DCMAKE_BUILD_TYPE=Release > "$FC_OUT/build-all.log" 2>&1
source install/pr75/local_setup.bash
colcon --log-base log/joint-point-all-test test --build-base build/pr75 \
  --packages-select flexcell_skills flexcell_mtc --executor sequential \
  --test-result-base "$FC_OUT/test-results" > "$FC_OUT/tests-all.log" 2>&1
colcon test-result --test-result-base "$FC_OUT/test-results" --verbose > "$FC_OUT/test-result-all.log" 2>&1
python3 setup/82_undefined_attr_check.py src/flexcell > "$FC_OUT/static-scan.log" 2>&1
python3 -m py_compile scripts/sim_smoke.py scripts/sim_window.py scripts/planner_snapshot_gate.py
git diff --quiet
tail -n 4 "$FC_OUT/build-all.log"
cat "$FC_OUT/test-result-all.log" "$FC_OUT/static-scan.log"
