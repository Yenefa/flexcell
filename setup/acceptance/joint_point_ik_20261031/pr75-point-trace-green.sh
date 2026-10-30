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
FC_OUT=/home/ros/agentic_workcell_ws/artifacts/joint-point-fix-20261031
colcon --log-base log/joint-point-trace build --merge-install --build-base build/pr75 --install-base install/pr75 \
  --packages-select flexcell_mtc --cmake-args -DCMAKE_BUILD_TYPE=Release > "$FC_OUT/build-trace.log" 2>&1
python3 -m pytest -q src/flexcell/flexcell_mtc/test/test_attached_point_plan.py -p no:cacheprovider \
  --basetemp "$FC_OUT/numerical-trace-green" > "$FC_OUT/numerical-trace-green.log" 2>&1
tail -n 8 "$FC_OUT/numerical-trace-green.log"
