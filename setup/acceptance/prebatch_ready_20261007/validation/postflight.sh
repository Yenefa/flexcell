#!/bin/bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/131_prebatch_readiness.py --live \
 --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261007_125924/deployment.json \
 --receipt setup/acceptance/composite_api_20261007 --receipt setup/acceptance/composite_resume_20261007 \
 --out /home/ros/fc_sync_logs/prebatch_ready_20261007/readiness_postflight.json
