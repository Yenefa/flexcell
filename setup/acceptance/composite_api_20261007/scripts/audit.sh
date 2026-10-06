#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/127_composite_audit.py \
 --receipt setup/acceptance/composite_api_20261007/execution/composite/parent.jsonl \
 --episodes setup/acceptance/composite_api_20261007/execution/composite/episodes \
 --deployment setup/acceptance/composite_api_20261007/plan/deployment.json
