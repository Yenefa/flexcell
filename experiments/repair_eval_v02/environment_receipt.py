"""Reproducible environment provenance without requiring a container image."""
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess

import health


def capture(overlay=None):
    receipt = {"source_kind": "host_receipt", "python": platform.python_version(),
               "platform": platform.platform(), "image_digest": None,
               "image_required": False, "dependencies": {}, "installed_files": {}}
    for name in ("pytest", "PyYAML"):
        try:
            receipt["dependencies"][name] = version(name)
        except PackageNotFoundError:
            receipt["dependencies"][name] = "NOT_INSTALLED"
    os_release = Path("/etc/os-release")
    if os_release.exists():
        receipt["os_release_sha256"] = health.file_sha(os_release)
        receipt["os_release"] = {line.split("=", 1)[0]: line.split("=", 1)[1].strip('"')
                                 for line in os_release.read_text().splitlines()
                                 if line.startswith(("PRETTY_NAME=", "VERSION_ID="))}
    for root in (Path("/opt/ros/jazzy"), Path(overlay) if overlay else None):
        if root is None or not root.is_dir():
            continue
        files = [root / "setup.bash", root / ".colcon_install_layout"]
        files += ([root / "share" / name / "package.xml" for name in
                   ("ros_environment", "ros_gz_sim", "gz_sim_vendor", "rclpy",
                    "moveit_configs_utils")] if root.name == "jazzy" else
                  list(root.glob("*/share/*/package.xml")))
        for path in files:
            if path.is_file():
                receipt["installed_files"][str(path)] = health.file_sha(path)
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\n",
             "ros-jazzy-ros-base", "ros-jazzy-gz-sim-vendor", "ros-jazzy-ros-gz-sim"],
            capture_output=True, text=True, timeout=5)
        receipt["ros_gazebo_packages"] = result.stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired):
        receipt["ros_gazebo_packages"] = "NOT_AVAILABLE"
    receipt["overlay_relation_to_candidate"] = "NOT_VERIFIED; installed metadata only, no build performed"
    body = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt["receipt_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    return receipt
