#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
python3 -m pytest src/flexcell/flexcell_skills/test/test_composite.py src/flexcell/flexcell_skills/test/test_composite_server.py -v
