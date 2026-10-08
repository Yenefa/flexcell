#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
if [ "$ROS_DOMAIN_ID" != 45 ]; then exit 2; fi
python3 setup/131_prebatch_readiness.py --live --workspace /home/ros/agentic_workcell_ws --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261008_004906/deployment.json --out /home/ros/fc_sync_logs/grasp_diagnostic_school_20261008/readiness.json
