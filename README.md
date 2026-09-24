# Agentic Flexible Robotic Workcell

ROS 2 Jazzy workcell around a ROBOTIS **OpenMANIPULATOR-X**, simulated in
Gazebo Harmonic and planned/executed through MoveIt 2.

## Status - Day 1 complete

| Item | State |
|---|---|
| Ubuntu 24.04 + ROS 2 Jazzy | OK |
| Gazebo Harmonic 8.15.0 | OK |
| OpenMANIPULATOR-X (ROBOTIS jazzy source) | OK, 6 colcon packages |
| Gazebo model + 3 controllers active | OK |
| MoveIt 2 Plan | OK, error_code = 1 |
| MoveIt 2 Execute | OK, error_code = 1 |
| Real motion in Gazebo physics | OK, verified via link poses |
| /joint_states consistent with plan | OK |

See DAY1_REPORT.md for the full environment, every problem hit, and the fixes.

## Layout

    agentic_workcell_ws/
    |- DAY1_REPORT.md          # Day 1 report
    |- plan_execute.py         # MoveIt Plan & Execute driver
    |- agentic_workcell.repos  # upstream repos (vcstool)
    |- scripts/                # provisioning + launch scripts
    |- src/                    # upstream sources (not tracked)

## Reproduce

    mkdir -p ~/agentic_workcell_ws/src && cd ~/agentic_workcell_ws
    vcs import src < agentic_workcell.repos
    source /opt/ros/jazzy/setup.bash
    rosdep install --from-paths src --ignore-src -r -y
    colcon build --symlink-install \
      --packages-up-to open_manipulator_bringup open_manipulator_moveit_config

## Run

    # Terminal 1 - Gazebo
    ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py

    # Terminal 2 - MoveIt 2 + RViz
    ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true

    # Terminal 3 - Plan & Execute (optional joint target)
    python3 plan_execute.py 0.6 -0.9 0.9 0.5

## Known limitations

- WSL exposes no /dev/dri and the WSL dxg graphics path currently fails
  (dxgkio_query_adapter_info: Ioctl failed: -22), so Gazebo/RViz render on CPU
  (llvmpipe). Simulation is unaffected; only the GUI is slow.
- CUDA toolkit is intentionally NOT installed - nothing on Day 1 needs it.
