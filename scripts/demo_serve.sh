#!/usr/bin/env bash
# Start the demo stack plus a Gazebo GUI and keep it alive.
#
# Usage: scripts/demo_serve.sh SOURCE_RUN_DIR OUT_DIR
# Env: DEMO_GUI=gpu|soft (default soft). GPU uses Mesa D3D12; if the driver
# segfaults, fall back to soft (llvmpipe).
set +u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC=${1:?source run dir}
OUT=${2:-/tmp/demo-serve}
rm -rf /tmp/demo-ready
mkdir -p "$OUT"

pkill -f "ros2 launch flexcell_skills" 2>/dev/null || true
pkill -f "flexcell_skills/" 2>/dev/null || true
pkill -f "gz sim" 2>/dev/null || true
pkill -f "move_group" 2>/dev/null || true
sleep 4

cd "$REPO" || exit 1
. /opt/ros/jazzy/setup.bash
. install/setup.bash
export FLEXCELL_REPO="$REPO" FLEXCELL_WS="$REPO" FLEXCELL_INSTALL="$REPO/install"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=45
export GZ_PARTITION=pp-video
if [ "${DEMO_GUI:-soft}" = "gpu" ]; then
  export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
  unset LIBGL_ALWAYS_SOFTWARE
else
  export LIBGL_ALWAYS_SOFTWARE=1
  unset GALLIUM_DRIVER MESA_D3D12_DEFAULT_ADAPTER_NAME
fi

nohup ros2 launch flexcell_skills trusted_sim.launch.py \
  world:="$SRC/world.sdf" params_file:="$SRC/params.yaml" camera:=false \
  > "$OUT/stack.log" 2>&1 &
for i in $(seq 1 60); do
  ros2 action list 2>/dev/null | grep -q /run_demo && break
  sleep 2
done
ros2 action list 2>/dev/null | grep -q /run_demo || { echo "no /run_demo server" >&2; exit 3; }

QT_QPA_PLATFORM=xcb GDK_BACKEND=x11 nohup gz sim -g > "$OUT/gui.log" 2>&1 &
sleep 15

python3 setup/flexcell_admin.py reset > "$OUT/reset_before.json" 2>&1
grep -o '"ok": *[a-z]*' "$OUT/reset_before.json" | head -1
touch /tmp/demo-ready
while true; do sleep 5; done
