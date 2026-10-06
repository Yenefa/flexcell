#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/transferbench/t3_swap_pilot.py run-arm --arm fsm \
  --root /home/ros/agentic_workcell_ws/setup/acceptance/transferbench_t3_20261006
