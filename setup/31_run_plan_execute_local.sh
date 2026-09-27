#!/usr/bin/env bash
# Local adaptation of 31_run_plan_execute.sh (original copies from /mnt/a/WSL/setup/, this machine uses F:\flexcell-stage).
set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
set -u
cp /mnt/f/flexcell-stage/setup/30_plan_execute.py /home/ros/agentic_workcell_ws/plan_execute.py
exec python3 /home/ros/agentic_workcell_ws/plan_execute.py
