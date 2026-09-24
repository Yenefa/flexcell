#!/usr/bin/env bash
# Clone + build ROBOTIS OpenMANIPULATOR-X (jazzy branch) into ~/agentic_workcell_ws
# RUN AS USER 'ros' (has passwordless sudo).
set -euo pipefail

WS="$HOME/agentic_workcell_ws"
mkdir -p "$WS/src"
cd "$WS/src"

clone() {
  local repo="$1" branch="$2" dir="$3" i
  if [ -d "$dir/.git" ]; then echo "--- $dir already present"; return 0; fi
  for i in 1 2 3 4 5; do
    echo "--- clone $repo ($branch) -> $dir (attempt $i)"
    if git clone -b "$branch" --depth 1 "https://github.com/ROBOTIS-GIT/$repo.git" "$dir"; then return 0; fi
    rm -rf "$dir"; sleep 5
  done
  echo "!!! clone failed: $repo"; return 1
}

clone DynamixelSDK                 jazzy DynamixelSDK
clone dynamixel_interfaces         jazzy dynamixel_interfaces
clone dynamixel_hardware_interface jazzy dynamixel_hardware_interface
clone open_manipulator             jazzy open_manipulator

# Day-1 DoD only needs bringup + description + moveit_config.
# GUI / playground / teleop / collision / custom controllers are out of scope (Qt5, etc).
for pkg in open_manipulator open_manipulator_gui open_manipulator_playground open_manipulator_teleop open_manipulator_collision ros2_controller; do
  if [ -d "$WS/src/open_manipulator/$pkg" ]; then
    touch "$WS/src/open_manipulator/$pkg/COLCON_IGNORE"
    echo "--- COLCON_IGNORE -> $pkg"
  fi
done

echo "--- tree ---"
find "$WS/src" -maxdepth 2 -name package.xml | sort

# ROS setup.bash touches unset vars -> must disable nounset while sourcing
set +u
source /opt/ros/jazzy/setup.bash
set -u

# rosdep must reach the TUNA rosdistro mirror directly (Clash throttles it)
export no_proxy="${no_proxy:-},mirrors.tuna.tsinghua.edu.cn,mirrors.ustc.edu.cn"
export NO_PROXY="${NO_PROXY:-},mirrors.tuna.tsinghua.edu.cn,mirrors.ustc.edu.cn"

echo "=== rosdep update ==="
for i in 1 2 3 4 5; do rosdep update && break || { echo "rosdep update retry $i"; sleep 5; }; done

echo "=== rosdep install ==="
rosdep install --from-paths "$WS/src" --ignore-src -r -y

echo "=== colcon build ==="
cd "$WS"
colcon build --symlink-install \
  --packages-up-to open_manipulator_bringup open_manipulator_moveit_config \
  --cmake-args -DCMAKE_BUILD_TYPE=Release

echo "=== build done ==="
ls "$WS/install"
