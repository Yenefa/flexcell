#!/bin/bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/acceptance/prebatch_ready_20261007/scripts/adjudicate_control.py
python3 setup/acceptance/prebatch_ready_20261007/scripts/continue_registered.py
