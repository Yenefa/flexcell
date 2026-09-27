#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
echo "=== which links exist in gz model ==="
for L in link1 link2 link3 link4 link5 end_effector_link gripper_left_link; do
  r=$(timeout 5 gz model -m open_manipulator_x -l "$L" 2>&1 | head -2 | tr '\n' ' ')
  echo "$L => $r"
done
echo "=== end_effector joint in urdf ==="
grep -B2 -A6 "end_effector_link" /home/ros/agentic_workcell_ws/src/open_manipulator/open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x_arm.urdf.xacro | head -20
echo "LINK_PROBE_DONE"
