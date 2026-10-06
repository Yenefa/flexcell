#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
colcon test --packages-select flexcell_skills --event-handlers console_direct+
colcon test-result --test-result-base build/flexcell_skills
