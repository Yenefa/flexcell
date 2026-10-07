#!/bin/bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
colcon build --base-paths src --symlink-install --packages-select flexcell_skills
