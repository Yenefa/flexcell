#!/usr/bin/env bash
# Install ROS 2 Jazzy + Gazebo Harmonic integration + ros2_control + MoveIt 2. RUN AS ROOT.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt_update_retry() {
  local i
  for i in 1 2 3 4 5 6 7 8; do
    if apt-get update -y; then echo "[apt-get update OK attempt $i]"; return 0; fi
    echo "[apt-get update attempt $i failed, retry in 5s]"; sleep 5
  done
  echo "[apt-get update FAILED after 8 attempts]"; return 1
}
apt_install_retry() {
  local i
  for i in 1 2 3 4 5; do
    if apt-get install -y "$@"; then echo "[apt-get install OK attempt $i]"; return 0; fi
    echo "[apt-get install attempt $i failed, retry in 5s]"; sleep 5
    apt-get -f install -y || true
  done
  echo "[apt-get install FAILED after 5 attempts: $*]"; return 1
}

CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-noble}")
ARCH=$(dpkg --print-architecture)
echo "codename=${CODENAME} arch=${ARCH}"

echo "=== [1/6] universe ==="
add-apt-repository -y universe
apt_update_retry

echo "=== [2/6] ROS 2 apt source ==="
if [ ! -s /usr/share/keyrings/ros-archive-keyring.gpg ]; then
  curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
fi
cat > /etc/apt/apt.conf.d/99-mirror-direct <<'EOF'
Acquire::http::Proxy::mirrors.ustc.edu.cn "DIRECT";
Acquire::https::Proxy::mirrors.ustc.edu.cn "DIRECT";
Acquire::http::Proxy::mirrors.tuna.tsinghua.edu.cn "DIRECT";
Acquire::https::Proxy::mirrors.tuna.tsinghua.edu.cn "DIRECT";
EOF
echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.ustc.edu.cn/ros2/ubuntu ${CODENAME} main" \
  > /etc/apt/sources.list.d/ros2.list
apt_update_retry
echo "--- candidate check ---"
apt-cache policy ros-jazzy-desktop > /tmp/ros_candidate.txt 2>&1 || true; head -4 /tmp/ros_candidate.txt

echo "=== [3/6] ROS 2 Jazzy desktop + dev tools ==="
apt_install_retry ros-jazzy-desktop ros-dev-tools
apt_install_retry python3-colcon-common-extensions python3-vcstool python3-rosdep

echo "=== [4/6] ros2_control + ros_gz (Gazebo Harmonic) ==="
apt_install_retry ros-jazzy-ros2-control ros-jazzy-ros2-controllers ros-jazzy-controller-manager ros-jazzy-gz-ros2-control ros-jazzy-joint-state-publisher ros-jazzy-joint-state-publisher-gui ros-jazzy-xacro ros-jazzy-robot-state-publisher

if ! apt-get install -y ros-jazzy-ros-gz ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge; then
  echo "!!! ros-gz failed, adding OSRF Gazebo Harmonic apt repo and retrying"
  curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
    -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
  echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable ${CODENAME} main" \
    > /etc/apt/sources.list.d/gazebo-stable.list
  apt_update_retry
  apt_install_retry ros-jazzy-ros-gz ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge
fi

echo "=== [5/6] MoveIt 2 ==="
apt_install_retry ros-jazzy-moveit

echo "=== [6/6] rosdep init ==="
rosdep init || true
echo "=== ROS Jazzy install done ==="
