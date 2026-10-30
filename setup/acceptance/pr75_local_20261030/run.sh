#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/pr75/setup.bash
export FC_OUT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/artifacts/local-pr75-20261030
FC_SOURCE=/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https/work/pr75-ik
python3 "$FC_SOURCE/prepare.py" | tee "$FC_OUT/ik-fixture.log"
cmake -S "$FC_SOURCE" -B /home/ros/agentic_workcell_ws/build/pr75-ik -DCMAKE_BUILD_TYPE=Release \
  2>&1 | tee "$FC_OUT/ik-cmake.log"
cmake --build /home/ros/agentic_workcell_ws/build/pr75-ik --parallel 2 \
  2>&1 | tee "$FC_OUT/ik-build.log"
export AMENT_PREFIX_PATH="$FC_OUT/ik-probe/model-prefix:$AMENT_PREFIX_PATH"
export ROS_DOMAIN_ID=74 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
/home/ros/agentic_workcell_ws/build/pr75-ik/ik_probe --ros-args \
  --params-file "$FC_OUT/ik-probe/probe-params.yaml" \
  > "$FC_OUT/ik-probe/attempts.jsonl" 2> "$FC_OUT/ik-probe/stderr.log"
tail -n 1 "$FC_OUT/ik-probe/attempts.jsonl"
