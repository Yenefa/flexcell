#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/pr75-locked-upstream/setup.bash
source /home/ros/agentic_workcell_ws/install/pr75/local_setup.bash
export PYTHONDONTWRITEBYTECODE=1
FC_TOOLS=/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https/work
FC_ROOT=/home/ros/agentic_workcell_ws/artifacts/joint-point-runtime-20261031
test -f "$FC_ROOT/joint-window/window.json"
python3 "$FC_TOOLS/pr75-fixed-point-fk.py" > "$FC_ROOT/fk-audit.log" 2>&1
python3 "$FC_TOOLS/pr75-fixed-point-audit.py" > "$FC_ROOT/../joint-point-post-audit-v2.log" 2>&1
cat "$FC_ROOT/fk-audit.log"
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(json.dumps({"core_status":r["core_status"],"joint_status":r["joint"]["window_status"],"raw_steps":r["joint"]["all_raw_steps"],"remaining_processes":r["remaining_runtime_processes"]},indent=2))' "$FC_ROOT/local-audit.json"
