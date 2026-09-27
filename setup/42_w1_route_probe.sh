#!/usr/bin/env bash
echo "=== existing gazebo tags in URDF ==="
grep -n "<gazebo" /home/ros/agentic_workcell_ws/src/open_manipulator/open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x.urdf | head -6
echo "=== how bringup spawns robot + world ==="
sed -n '30,90p' /home/ros/agentic_workcell_ws/src/open_manipulator/open_manipulator_bringup/launch/open_manipulator_x_gazebo.launch.py
echo "=== locate empty_world.sdf ==="
find /opt/ros/jazzy/opt/gz_sim_vendor -name "empty_world.sdf" 2>/dev/null | head -2
echo "RECON_DONE"
