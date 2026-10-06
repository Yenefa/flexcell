#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
colcon build --symlink-install --packages-select flexcell_skills
colcon test --packages-select flexcell_skills --event-handlers console_direct+
colcon test-result --verbose
