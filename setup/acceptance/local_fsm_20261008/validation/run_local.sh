#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
test "$ROS_DOMAIN_ID" = 45
export PYTHONDONTWRITEBYTECODE=1
python3 setup/acceptance/local_fsm_20261008/scripts/registered_local.py "$1"
