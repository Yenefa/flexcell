#!/usr/bin/env bash
# Environment audit - run inside the Ubuntu 24.04 distro
echo "=== OS ==="; grep -E 'PRETTY_NAME|VERSION_ID|VERSION_CODENAME' /etc/os-release
echo "=== ROS_DISTRO ==="; echo "${ROS_DISTRO:-<unset>}"
echo "=== /opt/ros ==="; ls /opt/ros 2>/dev/null || echo "<none>"
echo "=== ros2 ==="; command -v ros2 || echo "<missing>"
echo "=== gz ==="; command -v gz || echo "<missing>"; gz sim --version 2>/dev/null || true
echo "=== colcon ==="; command -v colcon || echo "<missing>"
echo "=== rosdep ==="; command -v rosdep || echo "<missing>"
echo "=== git ==="; command -v git || echo "<missing>"
echo "=== nvidia ==="; command -v nvidia-smi >/dev/null && nvidia-smi -L || echo "<no nvidia-smi>"
echo "=== display ==="; echo "DISPLAY=${DISPLAY:-<unset>} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<unset>} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-<unset>}"
echo "=== /mnt/a ==="; ls /mnt/a 2>/dev/null | head -5 || echo "<no /mnt/a>"
echo "=== mem ==="; free -h
echo "=== cpu ==="; nproc
