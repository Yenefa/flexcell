#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
read -r baseline executor < <(python3 -c 'import json; x=json.load(open("/home/ros/fc_sync_logs/transferbench_t3_20261006/revisions.json")); print(x["baseline"],x["executor"])')
python3 setup/transferbench/t3_swap_pilot.py register \
  --root /home/ros/agentic_workcell_ws/setup/acceptance/transferbench_t3_20261006 \
  --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261006_232555/deployment.json \
  --baseline-revision "$baseline" --executor-revision "$executor" \
  --development /home/ros/fc_sync_logs/transferbench_t3_20261006/shared_development.json
