"""P1.4: drive a real Gazebo/ROS 2 task through sim_smoke and collect evidence."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
if [ -n "__EXTRA__" ]; then source "__EXTRA__"; fi
export GZ_PARTITION=flexcell-p14-$$ RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=61 LIBGL_ALWAYS_SOFTWARE=1
export FLEXCELL_REPO="$REPO" FLEXCELL_WS="$WS" FLEXCELL_INSTALL="__INSTALL__"
OUT=__OUT__
rm -rf "$OUT"; mkdir -p "$OUT"
cd "$REPO"
timeout -k 10 __TIMEOUT__ python3 scripts/sim_smoke.py --out "$OUT" --case __CASE__ --backend velocity_servo --skill-backend legacy __POSE__ __ZONE2__ __CFG__ > /tmp/p14-smoke.log 2>&1
echo "SMOKE_RC=$?"
ls "$OUT"
"""


def _wsl(path):
    """Translate a Windows path to the WSL view; WSL paths pass through."""
    posix = path.replace("\\", "/")
    if len(posix) > 2 and posix[1] == ":" and posix[2] == "/":
        return "/mnt/" + posix[0].lower() + posix[2:]
    return posix


DISTRO = os.environ.get("FLEXCELL_WSL_DISTRO", "Ubuntu-24.04")


def _to_wsl_path(host_path):
    """Host path -> path usable inside the target environment.

    A Windows path is translated through /mnt/<drive>; a path that is already
    POSIX (the harness running inside WSL) is returned unchanged. Doing
    split(":", 1)[1] unconditionally raised IndexError on every POSIX path.
    """
    normalized = str(host_path).replace("\\", "/")
    if len(normalized) > 1 and normalized[1] == ":" and normalized[0].isalpha():
        return "/mnt/" + normalized[0].lower() + normalized[2:]
    return normalized


def _bash(*args):
    """Command prefix that runs a bash command on the target distro.

    On the Windows host this goes through the `wsl` launcher. Inside WSL there is
    no `wsl` binary, so the same command runs directly - otherwise every
    run_execution call failed with FileNotFoundError: wsl and the agent never saw
    a single Gazebo result.
    """
    if os.environ.get("WSL_DISTRO_NAME") or not shutil.which("wsl"):
        return ["bash"] + list(args)
    return ["wsl", "-d", DISTRO] + ["--", "bash"] + list(args)


def run_smoke(repo_src, repo, ws, out, case="normal", distro="Ubuntu-24.04",
              timeout_s=600, build=True, place_pose=None, zone_2_pose=None, config_override=None,
              extra_setup=None, install_override=None):
    script = (SCRIPT
              .replace("__REPO__", repo)
              .replace("__WS__", ws)
              .replace("__SRC__", _wsl(repo_src))
              .replace("__OUT__", out)
              .replace("__CASE__", case)
              .replace("__TIMEOUT__", str(timeout_s))
              .replace("__BUILD__", "1" if build else "0")
              .replace("__POSE__", ("--place-pose " + " ".join(str(v) for v in place_pose)) if place_pose else "")
              .replace("__ZONE2__", ("--zone-2-pose " + " ".join(str(v) for v in zone_2_pose)) if zone_2_pose else "")
              .replace("__CFG__", ("--config-override " + _wsl(str(config_override))) if config_override else "")
              .replace("__EXTRA__", extra_setup or "")
              .replace("__INSTALL__", install_override or ("$WS/install")))
    fd, host_path = tempfile.mkstemp(suffix=".sh", text=True)
    os.close(fd)
    Path(host_path).write_text(script, encoding="utf-8", newline="\n")
    # The harness runs on the host, but a caller inside WSL (Linux python) has
    # no drive letter, so `split(":")` used to raise IndexError and the agent saw
    # "run_execution -> ERROR IndexError" instead of a Gazebo failure. Accept both:
    # a Windows temp path is translated, an already-POSIX path is used as-is.
    wsl_path = _to_wsl_path(host_path)
    # A fresh VM per gate removes stale ROS/Gazebo state between judge gates.
    if shutil.which("wsl"):
        subprocess.run(["wsl", "--shutdown"], capture_output=True, text=True,
                       timeout=120)
    time.sleep(3)
    proc = subprocess.run(_bash(wsl_path),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout_s + 300)
    # Inside WSL there is no VM to reset (no `wsl --shutdown`), so stale ROS /
    # Gazebo processes from an earlier execution survive and the next launch
    # returns HARNESS_ERROR with physical_tasks_dispatched=0. Clean BEFORE too.
    if not shutil.which("wsl"):
        # Deeper than the first attempt: after a long agent session the judge
        # launch still failed (HARNESS_ERROR, physical_tasks_dispatched=0).
        # The likely leftovers are not just gz sim - the gz ruby launcher, the
        # ROS daemon cache and stale FAST-DDS shared-memory segments survive too,
        # and a dead daemon makes the next launch see no nodes.
        subprocess.run(_bash("-lc",
                        "pkill -9 -f '[g]z ' 2>/dev/null; "
                        "pkill -9 -f '[r]uby.*gz' 2>/dev/null; "
                        "pkill -9 -f '[m]ove_group' 2>/dev/null; "
                        "pkill -9 -f '[t]ask_fsm_server' 2>/dev/null; "
                        "pkill -9 -f '[r]os2 launch' 2>/dev/null; "
                        "pkill -9 -f '[r]obot_state_publisher' 2>/dev/null; "
                        "pkill -9 -f '[c]ontroller_manager' 2>/dev/null; "
                        "ros2 daemon stop >/dev/null 2>&1; "
                        "rm -rf /dev/shm/fastrtps_* /dev/shm/sem.fastrtps_* 2>/dev/null; "
                        "sleep 3"),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90)

    # A gate may leave a simulator or node behind; the next gate must start clean.
    subprocess.run(_bash("-lc",
                    "pkill -9 -f '[g]z sim' 2>/dev/null; pkill -9 -f '[m]ove_group' 2>/dev/null; "
                    "pkill -9 -f '[t]ask_fsm_server' 2>/dev/null; pkill -9 -f '[s]im_smoke' 2>/dev/null; "
                    "pkill -9 -f '[r]os2 launch' 2>/dev/null; pkill -9 -f '[r]obot_state_publisher' 2>/dev/null; "
                    "for i in $(seq 1 40); do pgrep -f '[g]z sim' >/dev/null || break; sleep 1; done; "
                    "sleep 5"),
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=120)
    return {"returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-4000:]}


def build_source(package_src, wsl_ws="/home/ros/w5src-ws", distro="Ubuntu-24.04", timeout_s=900):
    """Build an agent-edited skill package into an isolated overlay workspace."""
    src = _wsl(str(package_src))
    script = ("#!/bin/bash\n"
              "set -e\n"
              "mkdir -p " + wsl_ws + "/src\n"
              "rm -rf " + wsl_ws + "/repo\n"
              "rsync -a --delete " + src + "/ " + wsl_ws + "/src/flexcell_skills/\n"
              "source /opt/ros/jazzy/setup.bash\n"
              "source /home/ros/agentic_workcell_ws/install/setup.bash\n"
              "cd " + wsl_ws + "\n"
              "colcon build --symlink-install --merge-install --packages-select flexcell_skills "
              "> /tmp/w5src-build.log 2>&1\n"
              "STAGE=" + wsl_ws + "-repo\n"
              "mkdir -p $STAGE/src/flexcell\n"
              "rsync -a --exclude=.git --exclude=build --exclude=install --exclude=log "
              "/home/ros/flexcell-p14/ $STAGE/\n"
              "rsync -a --delete " + src + "/ $STAGE/src/flexcell/flexcell_skills/\n"
              "echo BUILD_OK\n")
    fd, host_path = tempfile.mkstemp(suffix=".sh", text=True)
    os.close(fd)
    Path(host_path).write_text(script, encoding="utf-8", newline="\n")
    wsl_path = _to_wsl_path(host_path)
    command = (["bash", wsl_path] if host_path.startswith("/")
               else _bash(wsl_path))
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "build timeout"}
    return {"returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-3000:],
            "stderr": (proc.stderr or "")[-3000:],
            "setup": wsl_ws + "/install/setup.bash",
            "install": wsl_ws + "/install",
            "repo": wsl_ws + "-repo"}


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
    dest_wsl = _to_wsl_path(dest)
    script = "#!/bin/bash\nset -e\nrm -rf " + dest_wsl + "\nmkdir -p " + dest_wsl + "\ncp -r " + run_out + "/. " + dest_wsl + "/\n"
    fd, host_path = tempfile.mkstemp(suffix=".sh", text=True)
    os.close(fd)
    Path(host_path).write_text(script, encoding="utf-8", newline="\n")
    wsl_path = _to_wsl_path(host_path)
    proc = subprocess.run(_bash(wsl_path),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    return proc.returncode == 0


def latest(out_wsl, distro="Ubuntu-24.04"):
    proc = subprocess.run(_bash("-lc",
                                "ls -dt " + out_wsl + "/run-* 2>/dev/null | head -1"),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return (proc.stdout or "").strip()
