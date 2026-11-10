#!/usr/bin/env python3
"""Capture ground-truth final poses from a live Gazebo world.

WHY THIS IS NEEDED: the observation bridge reads skill logs, so it only knows about
objects the robot touched. T02 requires proving an object did NOT move - and an
untouched object never appears in a skill log. Reporting it as "absent" would fail a
correct run, and quietly assuming it stayed put would pass a wrong one. Neither is
acceptable, so the observation needs ground truth for every declared object.

This reads the gz Pose_V stream through the same helper the skill servers use, so it
sees exactly what the robot sees, not a separate simulation of the truth.
"""
import json
import sys
from pathlib import Path


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: capture_ground_truth.py <out.json> <model> [<model> ...]",
              file=sys.stderr)
        return 2
    out, names = Path(argv[0]), argv[1:]
    sys.path.insert(0, "/home/ros/flexcell-p14/src/flexcell/flexcell_skills")
    from flexcell_skills.common import sample_gz_pose

    objects, errors = {}, {}
    for name in names:
        pose, err = sample_gz_pose(name, timeout_s=8.0)
        if pose is None:
            errors[name] = err
            continue
        position, _quat = pose
        objects[name] = [round(float(position[0]), 6), round(float(position[1]), 6),
                         round(float(position[2]), 6), 0.0]
    payload = {"source": "GZ_GROUND_TRUTH", "objects": objects, "errors": errors}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("captured %d/%d objects" % (len(objects), len(names)))
    if errors:
        print("errors:", json.dumps(errors), file=sys.stderr)
    return 0 if objects else 1


if __name__ == "__main__":
    sys.exit(main())
