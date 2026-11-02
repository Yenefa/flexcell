#!/usr/bin/env bash
set -eo pipefail
FC_REPO=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone
FC_OUT=/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https/work/portable-native-20261101
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/build/preposition-world-stage/upstream/install/setup.bash
source /home/ros/agentic_workcell_ws/build/preposition-world-stage/install/local_setup.bash
export PYTHONDONTWRITEBYTECODE=1 ROS_DOMAIN_ID=46 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
cd "$FC_REPO"
python3 -m pytest -p no:cacheprovider src/flexcell/flexcell_skills/test/test_native_portable_sources.py \
  src/flexcell/flexcell_skills/test/test_native_cycle_window.py --junitxml="$FC_OUT/targeted-green.xml" \
  > "$FC_OUT/targeted-green.log" 2>&1
python3 -m pytest -p no:cacheprovider src/flexcell/flexcell_skills/test src/flexcell/flexcell_mtc/test \
  --junitxml="$FC_OUT/full-pytest.xml" > "$FC_OUT/full-pytest.log" 2>&1
python3 setup/82_undefined_attr_check.py src/flexcell > "$FC_OUT/static-scan.log" 2>&1
tail -n 4 "$FC_OUT/targeted-green.log"
tail -n 5 "$FC_OUT/full-pytest.log"
cat "$FC_OUT/static-scan.log"
