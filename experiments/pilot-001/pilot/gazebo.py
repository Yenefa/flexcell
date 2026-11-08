"""P1.4: drive a real Gazebo/ROS 2 task through sim_smoke and collect evidence."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = """#!/bin/bash
set -e
REPO=__REPO__
WS=__WS__
BUILD=__BUILD__
if [ "$BUILD" = "1" ]; then
  pkill -9 -f "gz sim" 2>/dev/null || true
  pkill -9 -f move_group 2>/dev/null || true
  pkill -9 -f task_fsm_server 2>/dev/null || true
  sleep 2
  rm -rf "$REPO" "$WS"; mkdir -p "$REPO" "$WS/src"
  rsync -a --exclude=.git --exclude=build --exclude=install --exclude=log __SRC__/ "$REPO"/
  ln -sfn "$REPO/src/flexcell" "$WS/src/flexcell"
  source /opt/ros/jazzy/setup.bash
  source /home/ros/agentic_workcell_ws/install/setup.bash
  cd "$WS"
  colcon build --merge-install --parallel-workers 6 --cmake-args -DCMAKE_BUILD_TYPE=Release > /tmp/p14-build.log 2>&1
fi
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
source "$WS/install/setup.bash"
export GZ_PARTITION=flexcell-p14-$$ RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=61 LIBGL_ALWAYS_SOFTWARE=1
export FLEXCELL_REPO="$REPO" FLEXCELL_WS="$WS" FLEXCELL_INSTALL="$WS/install"
OUT=__OUT__
rm -rf "$OUT"; mkdir -p "$OUT"
cd "$REPO"
timeout __TIMEOUT__ python3 scripts/sim_smoke.py --out "$OUT" --case __CASE__ --backend velocity_servo --skill-backend legacy __POSE__ __ZONE2__ > /tmp/p14-smoke.log 2>&1
echo "SMOKE_RC=$?"
ls "$OUT"
"""


def _wsl(path):
    return path.replace("\\", "/")


def run_smoke(repo_src, repo, ws, out, case="normal", distro="Ubuntu-24.04",
              timeout_s=600, build=True, place_pose=None, zone_2_pose=None):
    script = (SCRIPT
              .replace("__REPO__", repo)
              .replace("__WS__", ws)
              .replace("__SRC__", _wsl(repo_src))
              .replace("__OUT__", out)
              .replace("__CASE__", case)
              .replace("__TIMEOUT__", str(timeout_s))
              .replace("__BUILD__", "1" if build else "0")
              .replace("__POSE__", ("--place-pose " + " ".join(str(v) for v in place_pose)) if place_pose else "")
              .replace("__ZONE2__", ("--zone-2-pose " + " ".join(str(v) for v in zone_2_pose)) if zone_2_pose else ""))
    fd, host_path = tempfile.mkstemp(suffix=".sh", text=True)
    os.close(fd)
    Path(host_path).write_text(script, encoding="utf-8", newline="\n")
    wsl_path = "/mnt/c" + host_path.replace("\\", "/").split(":", 1)[1]
    proc = subprocess.run(["wsl", "-d", distro, "--", "bash", wsl_path],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout_s + 300)
    return {"returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-4000:]}


def collect(run_out):
    """Read the sim_smoke result.json and map it to pilot evidence items."""
    import glob
    files = sorted(glob.glob(os.path.join(run_out, "result.json")))
    if not files:
        files = sorted(glob.glob(os.path.join(run_out, "run-*", "result.json")))
    if not files:
        return {"found": False}
    doc = json.load(open(files[0], encoding="utf-8"))
    keep = {k: doc.get(k) for k in ("status", "case", "runtime_fingerprint", "world_sha256",
                                    "semantic_config_sha256", "physical_tasks_dispatched",
                                    "window_id", "goal_pose")}
    task = doc.get("task") or {}
    keep["task"] = {k: task.get(k) for k in ("outcome", "error_code", "detail",
                                             "final_position_error_m")}
    return {"found": True, "path": files[0], "summary": keep}


def export(run_out, dest, distro="Ubuntu-24.04"):
    """Copy the WSL run directory to a Windows path via /mnt/c."""
    dest_wsl = "/mnt/c" + dest.replace("\\", "/").split(":", 1)[1]
    script = "#!/bin/bash\nset -e\nrm -rf " + dest_wsl + "\nmkdir -p " + dest_wsl + "\ncp -r " + run_out + "/. " + dest_wsl + "/\n"
    fd, host_path = tempfile.mkstemp(suffix=".sh", text=True)
    os.close(fd)
    Path(host_path).write_text(script, encoding="utf-8", newline="\n")
    wsl_path = "/mnt/c" + host_path.replace("\\", "/").split(":", 1)[1]
    proc = subprocess.run(["wsl", "-d", distro, "--", "bash", wsl_path],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    return proc.returncode == 0


def latest(out_wsl, distro="Ubuntu-24.04"):
    proc = subprocess.run(["wsl", "-d", distro, "--", "bash", "-lc",
                           "ls -dt " + out_wsl + "/run-* 2>/dev/null | head -1"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (proc.stdout or "").strip()
