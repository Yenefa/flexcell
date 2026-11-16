"""Probe what the retained-scenario check (#253) actually needs on this machine.

WHY A SCRIPT
    "The simulation stack is ready" is a sentence that ages badly. Each of these
    checks either passes here or it does not, and the point of running them before
    a hold-out batch is to find out which, without spending a model token on it.

WHAT IT CHECKS
    1. Gazebo Sim is present and can be started headless (no GPU on this host).
    2. The OpenMANIPULATOR overlay is built, so the bringup launch exists.
    3. The arm can actually be spawned and its controllers brought up.

    (3) is the one that failed on 2026-11-16, so it is reported as a finding
    rather than as a boolean: the launch reaches "Entity creation successful" and
    then the controller spawner dies because /robot_description never appears.

Exit code is 0 when every check passes, 1 otherwise, so a batch runner can gate
on it instead of on a human's recollection.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SETUP = "/opt/ros/jazzy/setup.bash"
WS = Path.home() / "agentic_workcell_ws"


def run(cmd, timeout=60, shell=True):
    return subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                          timeout=timeout, executable="/bin/bash")


def sourced(command, timeout=60):
    return run("source %s >/dev/null 2>&1; source %s/install/setup.bash >/dev/null 2>&1; %s"
               % (SETUP, WS, command), timeout=timeout)


def check_gazebo():
    got = sourced("command -v gz; gz sim --versions")
    if got.returncode != 0 or not got.stdout.strip():
        return False, "gz not found after sourcing; got %r" % (got.stderr or got.stdout)[:200]
    lines = [l for l in got.stdout.strip().splitlines() if l.strip()]
    version = lines[-1].strip() if lines else "?"
    return True, "gz sim %s at %s" % (version, lines[0].strip() if lines else "?")


def check_overlay():
    if not (WS / "install" / "setup.bash").exists():
        return False, "%s/install/setup.bash is missing; the overlay was never built" % WS
    got = sourced("ros2 pkg list | grep -c '^open_manipulator' ; true")
    count = got.stdout.strip().splitlines()[-1] if got.stdout.strip() else "0"
    if count == "0":
        return False, "overlay present but exposes no open_manipulator packages"
    return True, "overlay built, %s open_manipulator packages visible" % count


def check_robot_description():
    """Start the bringup for a bounded time and look for the known failure."""
    if os.environ.get("SKIP_LAUNCH") == "1":
        return None, "skipped (SKIP_LAUNCH=1)"
    log = Path("/tmp/fc_holdout_probe.log")
    # Clear leftovers first. Twice on 2026-11-16 this check failed because an
    # earlier interrupted launch still held the world, and the failure looked
    # exactly like a broken bring-up. A probe that reports its own mess as the
    # environment's fault is worse than no probe.
    run("pkill -f 'gz sim' ; pkill -f robot_state_publisher ; sleep 2 ; true", timeout=30)
    cmd = ("source %s >/dev/null 2>&1; source %s/install/setup.bash >/dev/null 2>&1; "
           "timeout 40 ros2 launch open_manipulator_bringup "
           "open_manipulator_x_gazebo.launch.py > %s 2>&1" % (SETUP, WS, log))
    run(cmd, timeout=70)
    text = log.read_text(errors="replace") if log.exists() else ""
    spawned = "Entity creation successful" in text
    controllers = "Could not successfully call service /controller_manager/list_controllers" not in text
    if spawned and controllers:
        return True, "arm spawned and the controller manager answered"
    if spawned:
        return False, ("arm spawned, but controller_manager never received "
                       "/robot_description and the spawner died")
    return False, "the bringup never reached 'Entity creation successful'"


def main():
    results = {}
    ok = True
    skipped = False
    for name, fn in (("gazebo", check_gazebo), ("overlay", check_overlay),
                     ("robot_description", check_robot_description)):
        passed, detail = fn()
        results[name] = {"ok": passed, "detail": detail}
        if passed is False:
            ok = False
        elif passed is None:
            # A skipped check is not a passed check. Reporting ready=true because
            # the deciding check did not run is the false green this script exists
            # to avoid.
            skipped = True
        print("%-20s %-6s %s" % (name, "OK" if passed else ("SKIP" if passed is None else "FAIL"), detail))
    print(json.dumps({"ready": ok and not skipped, "incomplete": skipped,
                      "checks": results}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
