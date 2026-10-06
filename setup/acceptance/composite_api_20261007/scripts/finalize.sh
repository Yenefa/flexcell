#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 /home/ros/fc_sync_logs/composite_api_20261007/finalize_report.py
