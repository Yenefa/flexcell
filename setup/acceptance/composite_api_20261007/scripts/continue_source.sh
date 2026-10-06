#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/acceptance/composite_api_20261007/scripts/continue_source_only.py
