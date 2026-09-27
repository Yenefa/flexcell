#!/usr/bin/env bash
set +u
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
set -u
cp /mnt/a/WSL/setup/30_plan_execute.py /home/ros/agentic_workcell_ws/plan_execute.py
exec python3 /home/ros/agentic_workcell_ws/plan_execute.py
