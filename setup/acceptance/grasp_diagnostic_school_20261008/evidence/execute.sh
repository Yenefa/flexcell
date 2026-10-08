#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
if [ "$ROS_DOMAIN_ID" != 45 ]; then exit 2; fi
python3 /home/ros/fc_sync_logs/grasp_diagnostic_school_20261008/execute.py
