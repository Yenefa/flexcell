#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/transferbench/t1_pilot.py run-arm --root /home/ros/agentic_workcell_ws/setup/acceptance/transferbench_t1_20261006 --arm fsm
