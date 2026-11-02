#!/usr/bin/env bash
set -eo pipefail
FC_REPO=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone
FC_OUT=/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https/work/portable-native-20261101
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/build/preposition-world-stage/upstream/install/setup.bash
source /home/ros/agentic_workcell_ws/build/preposition-world-stage/install/local_setup.bash
export PYTHONDONTWRITEBYTECODE=1
cd "$FC_REPO"
code=0
python3 -m pytest -p no:cacheprovider src/flexcell/flexcell_skills/test/test_native_portable_sources.py \
  -vv --junitxml="$FC_OUT/red.xml" > "$FC_OUT/red.log" 2>&1 || code=$?
tail -n 8 "$FC_OUT/red.log"
test "$code" -eq 1
