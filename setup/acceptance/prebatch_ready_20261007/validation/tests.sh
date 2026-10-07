#!/bin/bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
PYTHONPATH=src/flexcell/flexcell_skills:src/flexcell/flexcell_skills/test:$PYTHONPATH python3 -m pytest src/flexcell/flexcell_skills/test -q
