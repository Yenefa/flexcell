#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
test "$ROS_DOMAIN_ID" = 45
PYTHONDONTWRITEBYTECODE=1 python3 setup/acceptance/bounded_runner_20261007/scripts/registered_pilot.py
