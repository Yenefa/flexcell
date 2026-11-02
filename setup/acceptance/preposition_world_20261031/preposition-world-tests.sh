#!/usr/bin/env bash
set -eo pipefail
FC_STAGE=/home/ros/agentic_workcell_ws/build/preposition-world-stage
FC_OUT=/home/ros/agentic_workcell_ws/artifacts/preposition-world-20261031
cp "$FC_OUT/tests.log" "$FC_OUT/tests-first-layout-error.log"
source /opt/ros/jazzy/setup.bash
source "$FC_STAGE/upstream/install/setup.bash"
source "$FC_STAGE/install/local_setup.bash"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PYTHONDONTWRITEBYTECODE=1
cd "$FC_STAGE"
colcon --log-base "$FC_OUT/test-log-corrected-layout" test --merge-install --build-base "$FC_STAGE/build" \
  --install-base "$FC_STAGE/install" --base-paths src/flexcell \
  --test-result-base "$FC_OUT/test-results" --executor sequential > "$FC_OUT/tests.log" 2>&1
colcon test-result --test-result-base "$FC_OUT/test-results" --verbose > "$FC_OUT/test-result.log" 2>&1
python3 setup/82_undefined_attr_check.py src/flexcell > "$FC_OUT/static-scan.log" 2>&1
cat "$FC_OUT/test-result.log" "$FC_OUT/static-scan.log"
