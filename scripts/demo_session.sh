#!/usr/bin/env bash
# Record a continuous demo: stack + GPU GUI + ffmpeg, then RunDemo cycles.
#
# Usage: scripts/demo_session.sh [SOURCE_RUN_DIR] [OUT_DIR]
# SOURCE_RUN_DIR must contain world.sdf and params.yaml (a previous sim run).
set +u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$(ls -dt /tmp/carry-window2/out/NORMAL_1/run-* 2>/dev/null | head -1)}"
OUT="${2:-$REPO/artifacts/demo-$(date +%Y%m%d-%H%M%S)}"

if [ ! -f "$SRC/world.sdf" ] || [ ! -f "$SRC/params.yaml" ]; then
  echo "source run dir missing world.sdf/params.yaml: $SRC" >&2
  exit 2
fi
mkdir -p "$OUT"

# a previous stack leaves nodes and DDS participants behind; clean before starting
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
export GZ_PARTITION=pp-demo
export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
unset LIBGL_ALWAYS_SOFTWARE

cleanup() {
  kill -INT "$FFMPEG_PID" 2>/dev/null || true
  pkill -f "ros2 launch flexcell_skills" 2>/dev/null || true
  pkill -f "flexcell_skills/" 2>/dev/null || true
  pkill -f "gz sim" 2>/dev/null || true
  pkill -f "move_group" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== stack ==="
nohup ros2 launch flexcell_skills trusted_sim.launch.py \
  world:="$SRC/world.sdf" params_file:="$SRC/params.yaml" camera:=false \
  > "$OUT/stack.log" 2>&1 &

for i in $(seq 1 60); do
  if ros2 action list 2>/dev/null | grep -q "/run_demo"; then break; fi
  sleep 2
done
ros2 action list 2>/dev/null | grep -q "/run_demo" || { echo "no /run_demo server" >&2; exit 3; }

echo "=== gui ==="
nohup gz sim -g > "$OUT/gui.log" 2>&1 &
sleep 10

SIZE=""
for candidate in 1920x1080 2560x1440 1280x720 1024x768; do
  if ffmpeg -hide_banner -loglevel error -y -f x11grab -video_size "$candidate" \
       -i :0 -frames:v 1 "$OUT/_probe.png" >/dev/null 2>&1; then
    SIZE="$candidate"; break
  fi
done
if [ -z "$SIZE" ]; then echo "x11grab found no usable screen size" >&2; exit 4; fi
rm -f "$OUT/_probe.png"
echo "recording at $SIZE"

echo "=== record + run demo ==="
ffmpeg -hide_banner -loglevel warning -y -f x11grab -framerate 30 -video_size "$SIZE" \
  -i :0 -c:v libx264 -preset veryfast -pix_fmt yuv420p "$OUT/demo.mp4" \
  > "$OUT/ffmpeg.log" 2>&1 &
FFMPEG_PID=$!
sleep 2

echo "=== canonical reset before the demo ==="
python3 setup/flexcell_admin.py reset > "$OUT/reset_before.json" 2>&1
grep -o '"ok": *[a-z]*' "$OUT/reset_before.json" | head -1

python3 "$REPO/scripts/run_demo_cycles.py" --out "$OUT" --cycles 2
RC=$?

sleep 2
kill -INT "$FFMPEG_PID" 2>/dev/null || true
wait "$FFMPEG_PID" 2>/dev/null || true
FFMPEG_PID=""

echo "=== artifacts ==="
ls -l "$OUT"
if command -v ffprobe >/dev/null; then
  ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT/demo.mp4"
fi
exit "$RC"
