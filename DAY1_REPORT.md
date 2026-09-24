# Day 1 Report — OpenMANIPULATOR-X · Gazebo Harmonic · MoveIt 2 Plan & Execute

**Status: DONE.** All six Definition-of-Done items verified on-machine.

## Definition of Done

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | ROS 2 Jazzy 正常 | PASS | `ROS_DISTRO=jazzy`, `ros2 pkg list` = 416 pkgs |
| 2 | Gazebo 中 OpenMANIPULATOR-X 正常出现 | PASS | `gz model --list` → `open_manipulator_x` |
| 3 | MoveIt 可以成功 Plan | PASS | `PLAN error_code = 1`, 14 waypoints, 0.019 s |
| 4 | MoveIt Execute 成功 | PASS | `EXECUTE error_code = 1` |
| 5 | Gazebo 中机械臂真实发生运动 | PASS | Gazebo transport `link2` quaternion → 0.597 rad = commanded `joint1` |
| 6 | joint_states 与执行结果一致 | PASS | planned final == after state == `[0.5971, -0.9069, 0.8919, 0.5064]` |

## Environment

- **Host**: Windows 11 家庭版 (build 26200), 16 threads / 16 GB RAM, NVIDIA RTX 4060 Laptop 8 GB (driver 580.88)
- **Runtime**: WSL2 2.7.3.0 + WSLg. **All new work lives on the A: drive.**
- **Distro**: Ubuntu 24.04.5 LTS (noble), user `ros`, VHDX at `A:\WSL\Ubuntu-24.04\ext4.vhdx`
- **ROS**: ROS 2 Jazzy (`ros-jazzy-desktop 0.11.0-1noble`)
- **Gazebo**: Harmonic **8.15.0** (shipped as ROS vendor pkgs — no OSRF apt repo needed)
- **MoveIt**: 2.12.4
- **Workspace**: `~/agentic_workcell_ws` (inside the A:-hosted VHDX)
- **Untouched**: the pre-existing `Ubuntu-22.04` + ROS **Humble** distro was never sourced or modified — no Humble/Jazzy mixing.

## Installed packages

```
ros-jazzy-desktop            ros-dev-tools          python3-colcon-common-extensions
ros-jazzy-ros2-control       ros-jazzy-ros2-controllers       ros-jazzy-controller-manager
ros-jazzy-gz-ros2-control    ros-jazzy-ros-gz                 ros-jazzy-ros-gz-sim
ros-jazzy-ros-gz-bridge      ros-jazzy-joint-state-publisher  ros-jazzy-xacro
ros-jazzy-robot-state-publisher      ros-jazzy-moveit (2.12.4)
ros-jazzy-gz-*-vendor (sim 8.15.0, transport, rendering, gui, physics, ogre-next, ...)
```

Built from source (ROBOTIS `jazzy` branches, `--symlink-install`):
`DynamixelSDK`, `dynamixel_interfaces`, `dynamixel_hardware_interface`, `open_manipulator`
→ 6 colcon packages: `dynamixel_sdk`, `dynamixel_interfaces`, `dynamixel_hardware_interface`,
`open_manipulator_description`, `open_manipulator_moveit_config`, `open_manipulator_bringup`

## Launch commands

```bash
# Terminal 1 — Gazebo
ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py

# Terminal 2 — MoveIt 2 + RViz
ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true

# Terminal 3 — Plan & Execute
python3 ~/agentic_workcell_ws/plan_execute.py
```

## Problems encountered & fixes

| # | Problem | Root cause | Minimal fix |
|---|---------|-----------|-------------|
| 1 | Target is Ubuntu 24.04 + Jazzy, host only had Ubuntu 22.04 + **Humble** | Missing environment | Installed a **separate** `Ubuntu-24.04` WSL distro, VHDX on A: |
| 2 | `wsl --install --vhdsize 200GB` → `E_INVALIDARG` | Flag not accepted by this WSL build | Dropped `--vhdsize`, used `--location A:\WSL\Ubuntu-24.04 --no-launch` |
| 3 | `apt-get update` → `502 Bad Gateway` on `noble-updates` | Flaky Clash proxy (127.0.0.1:7890) | `apt_update_retry` / `apt_install_retry` wrappers |
| 4 | Install script aborted right after the repo check | `set -o pipefail` + `apt-cache policy \| head -4` → SIGPIPE | Redirect to file, then `head` the file |
| 5 | Downloads crawling at ~15 KB/s | Clash proxy throttles `packages.ros.org` | ROS repo → **USTC mirror** + per-host `Acquire::*::Proxy "DIRECT"` → **~470 KB/s** |
| 6 | `rosdep init` → `SSL: UNEXPECTED_EOF` on raw.githubusercontent.com | Proxy breaks TLS to that host | Wrote `/etc/ros/rosdep/sources.list.d/20-default.list` against the **TUNA rosdistro** mirror |
| 7 | Build died at `source /opt/ros/jazzy/setup.bash` | `set -u` + unbound `AMENT_TRACE_SETUP_FILES` | `set +u` around the `source` |
| 8 | `moveit_py` unavailable | Not in `ros-jazzy-moveit` | Drove the native `/move_action` + `/execute_trajectory` actions (no extra install) |

## Final verification

```
BEFORE /joint_states: {'joint1': -0.0, 'joint2': 0.0, 'joint3': 0.0, 'joint4': 0.0}
PLAN    error_code = 1   planning_time = 0.0192   waypoints = 14   duration = 1.205 s
PLANNED final positions: [0.5971, -0.9069, 0.8919, 0.5064]
EXECUTE error_code = 1
AFTER  /joint_states: {'joint1': 0.5971, 'joint2': -0.9069, 'joint3': 0.8919, 'joint4': 0.5064}
DELTA  /joint_states: {'joint1': 0.5971, 'joint2': -0.9069, 'joint3': 0.8919, 'joint4': 0.5064}
MOTION_DETECTED = True

controllers: arm_controller [active]  gripper_controller [active]  joint_state_broadcaster [active]
gz model --list: ground_plane, open_manipulator_x
gz /world/empty/pose/info link2 orientation: z=0.29413 w=0.95577  ->  2*acos(0.95577) = 0.597 rad = joint1
```

## Reproduction commands

```powershell
# from Windows
wsl -d Ubuntu-24.04            # user 'ros'; ROS + workspace already sourced via ~/.bashrc
```

Setup scripts used (kept on A:): `A:\WSL\setup\`
`00_audit.sh`, `01_provision.sh`, `02_ros_jazzy.sh`, `03_build_omx.sh`,
`10_switch_mirror.sh`, `20_launch_gazebo.sh`, `22_launch_moveit.sh`,
`30_plan_execute.py`, `31_run_plan_execute.sh`

## Known limitations (not Day-1 blockers)

- WSL exposes **no `/dev/dri`**, so WSLg falls back to software GL: `gz sim gui` burns ~300% CPU.
  Simulation still ran the 1.2 s trajectory correctly. If the GUI feels sluggish, lower the
  render rate or run the server headless (`-s`) and keep RViz for visualisation.
- WSLg windows are hardware-composited, so GDI screen capture returns the desktop, not the
  window. Verify motion via `/joint_states` / `gz topic`, not screenshots.
- The arm is spawned at the zero pose; the MoveIt SRDF `home` is `[0, -1, 1, 0]`.
