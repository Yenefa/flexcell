#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/transferbench/t1_pilot.py register --root /home/ros/agentic_workcell_ws/setup/acceptance/transferbench_t1_20261006 --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261006_125822/deployment.json --revision d58f4f1d6854c6b74ab6c410dadd796cf991b592
