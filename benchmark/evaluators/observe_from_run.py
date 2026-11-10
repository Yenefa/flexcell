#!/usr/bin/env python3
"""Build an evaluator observation from a real Gazebo run.

WHY THIS FILE EXISTS: the independent evaluator grades an observation, but the robot
does not emit one. Without this bridge every verdict would be an opinion. It reads
only skill logs the runtime already writes, and it never reads the task spec - so it
cannot bias the observation toward what the task wanted.

SOURCE OF TRUTH, per object:
  - verify.jsonl  -> "measured": the object pose the verify skill actually measured
  - place.jsonl   -> "box_after": the pose right after release, used when a place
                     happened but no verify did
  - observe.jsonl -> "available": which objects were seen at all
  - pick.jsonl    -> order of picks, for the "ordered" clause

An object with no measured pose is reported as ABSENT rather than assumed to be at
its start position. Assuming it did not move is exactly the mistake that would turn
an unobserved object into a pass.
"""
import json
import sys
from pathlib import Path

ABSENT = None


def _read(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _xy_z_yaw(pose):
    if not pose or len(pose) < 3:
        return None
    return [round(float(pose[0]), 6), round(float(pose[1]), 6), round(float(pose[2]), 6), 0.0]


def _nearest_zone_name(pose, zones, tolerance=0.06):
    if not zones:
        return None
    best, best_d = None, None
    for name, zpose in zones.items():
        d = ((pose[0] - zpose[0]) ** 2 + (pose[1] - zpose[1]) ** 2) ** 0.5
        if best_d is None or d < best_d:
            best, best_d = name, d
    return best if best_d is not None and best_d <= tolerance else None


def build_observation(run_dir, declared_objects, agent_claimed_success=False,
                      ground_truth=None, zones=None):
    """Return the observation dict the evaluator consumes."""
    run = Path(run_dir)
    skills = run / "skills"
    verify = _read(skills / "verify.jsonl")
    place = _read(skills / "place.jsonl")
    observe = _read(skills / "observe.jsonl")
    pick = _read(skills / "pick.jsonl")

    measured, provenance = {}, {}
    # place.box_after is the earliest honest measurement of where a box ended up
    for row in place:
        name = row.get("object_name")
        pose = _xy_z_yaw(row.get("box_after"))
        if name and pose and row.get("released", True):
            measured[name] = pose
            provenance[name] = "place.box_after"
    # verify.measured overrides it: it is a later, dedicated measurement
    for row in verify:
        name = row.get("object_name")
        pose = _xy_z_yaw(row.get("measured"))
        if name and pose:
            measured[name] = pose
            provenance[name] = "verify.measured"

    # Ground truth wins: it covers objects the robot never touched, which is exactly
    # what a "must not move" clause needs. It comes from the live gz pose stream, the
    # same source the skill servers use, so it is not a second opinion invented here.
    gt_used = []
    if ground_truth:
        for name, pose in (ground_truth.get("objects") or {}).items():
            if name in declared_objects and pose:
                measured[name] = [float(v) for v in pose]
                provenance[name] = "gz.ground_truth"
                gt_used.append(name)

    seen = set()
    for row in observe:
        for name in (row.get("available") or []):
            seen.add(name)

    objects, absent = {}, []
    for name in declared_objects:
        if name in measured:
            objects[name] = measured[name]
        else:
            absent.append(name)

    # Route history: every release position this object passed through, mapped back to
    # the bin it landed in. This is what makes a relay template checkable.
    visits = {}
    for row in place:
        name = row.get("object_name")
        pose = _xy_z_yaw(row.get("box_after"))
        if not name or not pose or not row.get("released", True):
            continue
        zone_name = _nearest_zone_name(pose, zones or {})
        if zone_name:
            visits.setdefault(name, []).append(zone_name)

    sequence, picked = [], set()
    for row in pick:
        name = row.get("object_name")
        if name and name not in picked and row.get("outcome") in ("0", 0):
            sequence.append(name)
            picked.add(name)

    return {
        "objects": objects,
        "move_sequence": sequence,
        "agent_claimed_success": bool(agent_claimed_success),
        # Diagnostics for the analyst, ignored by the evaluator contract.
        "_provenance": provenance,
        "_absent": absent,
        "_ever_seen": sorted(seen),
        "_run_dir": str(run),
        "_ground_truth_used": sorted(gt_used),
        "visits": visits,
    }


def strip_diagnostics(observation):
    keep = {"objects", "move_sequence", "agent_claimed_success", "visits"}
    return {k: v for k, v in observation.items() if not k.startswith("_") and k in keep}


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 3:
        print("usage: observe_from_run.py <run_dir> <out.json> <object> [<object> ...]",
              file=sys.stderr)
        return 2
    run_dir, out_path, names = argv[0], argv[1], argv[2:]
    gt = None
    if "--ground-truth" in argv:
        gt_path = argv[argv.index("--ground-truth") + 1]
        names = [n for n in names if n != "--ground-truth" and n != gt_path]
        gt = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    zones = None
    if "--zones" in argv:
        zpath = argv[argv.index("--zones") + 1]
        try:
            zones = json.loads(zpath)
            names = [n for n in names if n not in ("--zones", zpath)]
        except json.JSONDecodeError:
            zones = json.loads(Path(zpath).read_text(encoding="utf-8"))
            names = [n for n in names if n not in ("--zones", zpath)]
    obs = build_observation(run_dir, names, ground_truth=gt, zones=zones)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    print("objects observed: %d/%d, absent: %s" % (
        len(obs["objects"]), len(names), obs["_absent"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
