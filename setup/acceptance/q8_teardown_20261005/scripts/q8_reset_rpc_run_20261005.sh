#!/usr/bin/env bash
set -eo pipefail
source /home/ros/agentic_workcell_ws/setup/104_mainline_env.sh
python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_reset_rpc_probe_20261005.py 2>&1 | tee /home/ros/agentic_workcell_ws/setup/acceptance/q8_teardown_20261005/reset_rpc_cold.log
