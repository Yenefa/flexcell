#!/usr/bin/env bash
# Provision the fresh Ubuntu 24.04 WSL distro. RUN AS ROOT.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

USERNAME=ros
USERPASS=ros

echo "=== [1/5] create user ${USERNAME} ==="
if ! id -u "${USERNAME}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash -G sudo "${USERNAME}"
  echo "${USERNAME}:${USERPASS}" | chpasswd
  echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-${USERNAME}
  chmod 0440 /etc/sudoers.d/90-${USERNAME}
fi

echo "=== [2/5] wsl.conf ==="
cat > /etc/wsl.conf <<'EOF'
[user]
default=ros
[automount]
enabled=true
options="metadata,umask=22,fmask=11"
[interop]
appendWindowsPath=false
EOF

echo "=== [3/5] locale UTF-8 ==="
apt-get update -y
apt-get install -y --no-install-recommends locales ca-certificates curl gnupg lsb-release
sed -i 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8

echo "=== [4/5] base toolchain ==="
apt-get install -y --no-install-recommends \
  git build-essential cmake python3-pip python3-venv python3-dev \
  software-properties-common wget unzip less nano

echo "=== [5/5] provision done ==="
id ${USERNAME}
