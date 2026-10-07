#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
[ "$ROS_DOMAIN_ID" = 45 ]
bash setup/102_mainline_runtime.sh switch hybrid 0.85
