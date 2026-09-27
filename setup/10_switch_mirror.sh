#!/usr/bin/env bash
# Switch ROS 2 apt source to a domestic mirror and force DIRECT (bypass Clash proxy).
set -uo pipefail
ARCH=$(dpkg --print-architecture)
CODENAME=noble

echo "=== stop any in-flight apt ==="
pkill -9 -f 'apt-get' 2>/dev/null || true
pkill -9 -f '/usr/lib/apt/methods' 2>/dev/null || true
sleep 3
pgrep -a apt || echo "(no apt running)"
rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock /var/lib/apt/lists/lock
dpkg --configure -a || true

echo "=== point ROS 2 source at USTC ==="
echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.ustc.edu.cn/ros2/ubuntu ${CODENAME} main" > /etc/apt/sources.list.d/ros2.list
cat /etc/apt/sources.list.d/ros2.list

echo "=== apt DIRECT for domestic mirrors ==="
cat > /etc/apt/apt.conf.d/99-mirror-direct <<'EOF'
Acquire::http::Proxy::mirrors.ustc.edu.cn "DIRECT";
Acquire::https::Proxy::mirrors.ustc.edu.cn "DIRECT";
Acquire::http::Proxy::mirrors.tuna.tsinghua.edu.cn "DIRECT";
Acquire::https::Proxy::mirrors.tuna.tsinghua.edu.cn "DIRECT";
EOF
cat /etc/apt/apt.conf.d/99-mirror-direct

echo "=== apt-get update ==="
for i in 1 2 3 4 5; do apt-get update -y && break || { echo "retry $i"; sleep 5; }; done
echo "=== candidate ==="
apt-cache policy ros-jazzy-desktop > /tmp/cand.txt 2>&1 || true
head -6 /tmp/cand.txt
echo "=== cache preserved ==="
du -sh /var/cache/apt/archives
