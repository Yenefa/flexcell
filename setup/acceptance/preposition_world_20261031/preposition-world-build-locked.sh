#!/usr/bin/env bash
set -eo pipefail
FC_STAGE=/home/ros/agentic_workcell_ws/build/preposition-world-stage
FC_OUT=/home/ros/agentic_workcell_ws/artifacts/preposition-world-20261031
FC_TOOLS=/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https/work
python3 "$FC_TOOLS/preposition-world-upstream.py" > "$FC_OUT/upstream-export.log" 2>&1
source /opt/ros/jazzy/setup.bash
export CMAKE_BUILD_PARALLEL_LEVEL=2 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export PYTHONDONTWRITEBYTECODE=1
colcon --log-base "$FC_OUT/upstream-build-log" build --merge-install --base-paths "$FC_STAGE/upstream/src" \
  --build-base "$FC_STAGE/upstream/build" --install-base "$FC_STAGE/upstream/install" --parallel-workers 2 \
  --packages-up-to open_manipulator_bringup open_manipulator_moveit_config \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF > "$FC_OUT/upstream-build.log" 2>&1
source "$FC_STAGE/upstream/install/setup.bash"
cd "$FC_STAGE"
dpkg-query -W > "$FC_OUT/dependency-packages.tsv"
colcon --log-base "$FC_OUT/build-log" build --merge-install --base-paths src/flexcell \
  --build-base "$FC_STAGE/build" --install-base "$FC_STAGE/install" --parallel-workers 2 \
  --cmake-args -DCMAKE_BUILD_TYPE=Release > "$FC_OUT/build.log" 2>&1
source "$FC_STAGE/install/local_setup.bash"
colcon --log-base "$FC_OUT/test-log" test --build-base "$FC_STAGE/build" --base-paths src/flexcell \
  --test-result-base "$FC_OUT/test-results" --executor sequential > "$FC_OUT/tests.log" 2>&1
colcon test-result --test-result-base "$FC_OUT/test-results" --verbose > "$FC_OUT/test-result.log" 2>&1
python3 setup/82_undefined_attr_check.py src/flexcell > "$FC_OUT/static-scan.log" 2>&1
tail -n 5 "$FC_OUT/upstream-build.log"
tail -n 5 "$FC_OUT/build.log"
cat "$FC_OUT/test-result.log" "$FC_OUT/static-scan.log"
