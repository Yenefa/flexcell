#!/usr/bin/env python3
"""Recheck the two things this batch's honesty rests on, from files on disk.

WHAT IT PROVES
    1. Whether the world that actually ran was spawned at the task instance's
       declared initial poses. If it was not, the trial did not run the declared
       task and its verdict is not a measurement of that task.
    2. The world-basis displacement, computed from ground truth poses the
       simulation actually produced, next to the spec-basis number the evaluator
       reports. The two differ exactly when the spawn differed, and only the
       world-basis number describes motion that happened.

WHY IT REFUSES RATHER THAN WARNS
    A checker that prints nothing when it finds nothing is indistinguishable
    from a checker that found nothing because it failed to parse. Every object
    and every pose here is required to be present and finite; a missing or
    unparseable pose is a hard failure with the reason, not a silent pass.
"""
import json
import math
import sys
from pathlib import Path

WT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")
EVIDENCE = WT / "setup/acceptance/evobot_t08_evidence_loop_20261112/evidence"

CASES = [
    ("R", "t1", None), ("R", "t2", None), ("R", "t3", None), ("R", "t4", None),
    ("R", "t5", None),
    ("S", "t1", None), ("S", "t2", None), ("S", "t3", None), ("S", "t4", None),
    ("S", "t5", None),
    ("U", "seed3000/t1", 3000), ("U", "seed3001/t1", 3001), ("U", "seed3002/t1", 3002),
    ("U_shot", "seed3000/t1", 3000), ("U_shot", "seed3001/t1", 3001),
    ("U_shot", "seed3002/t1", 3002),
]


def spec_for(seed):
    split = "t08_unseen" if seed >= 3000 else "t08_dev"
    path = WT / "benchmark" / "tasks" / split / ("T08-push-seed%d.json" % seed)
    if not path.is_file():
        raise SystemExit("REFUSED: spec not found for seed %d at %s" % (seed, path))
    return json.loads(path.read_text(encoding="utf-8"))


def poses(path):
    if not path.is_file():
        raise SystemExit("REFUSED: missing ground truth %s" % path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    objects = payload.get("objects") or {}
    for name, pose in objects.items():
        if not isinstance(pose, (list, tuple)) or len(pose) < 3:
            raise SystemExit("REFUSED: %s has malformed pose for %r" % (path, name))
        if not all(math.isfinite(float(v)) for v in pose[:3]):
            raise SystemExit("REFUSED: %s has non-finite pose for %r" % (path, name))
    if not objects:
        raise SystemExit("REFUSED: %s contains no object poses" % path)
    return objects


def main(argv):
    rows = []
    for arm, trial, seed in CASES:
        trial_dir = EVIDENCE / arm / trial
        spec_seed = seed if seed is not None else 2000
        spec = spec_for(spec_seed)
        before = poses(trial_dir / "gt_before.json")
        after = poses(trial_dir / "gt_after.json")
        worst_offset = 0.0
        for obj in spec["objects"]:
            name = obj["name"]
            if name not in before:
                raise SystemExit("REFUSED: %s/%s has no pre-pose for %r"
                                 % (arm, trial, name))
            want = obj["initial_pose"]
            have = before[name]
            worst_offset = max(worst_offset,
                               math.hypot(want[0] - have[0], want[1] - have[1]))
        target = spec["objects"][0]["name"]
        spec_start = [o for o in spec["objects"] if o["name"] == target][0]["initial_pose"]
        world_start = before[target]
        end = after[target]
        world_disp = math.hypot(end[0] - world_start[0], end[1] - world_start[1])
        spec_disp = math.hypot(end[0] - spec_start[0], end[1] - spec_start[1])
        rows.append(dict(arm=arm, trial=trial, seed=spec_seed,
                         offset_mm=worst_offset * 1000.0,
                         spec_disp_mm=spec_disp * 1000.0,
                         world_disp_mm=world_disp * 1000.0,
                         instantiated=worst_offset <= 0.001))

    print("%-7s %-12s %-6s %-12s %-12s %-12s %s"
          % ("arm", "trial", "seed", "offset_mm", "spec_disp", "world_disp",
             "instance_ran"))
    for row in rows:
        print("%-7s %-12s %-6d %-12.2f %-12.2f %-12.2f %s"
              % (row["arm"], row["trial"], row["seed"], row["offset_mm"],
                 row["spec_disp_mm"], row["world_disp_mm"],
                 "YES" if row["instantiated"] else "NO - INVALID_INFRA"))

    broken = [r for r in rows if not r["instantiated"]]
    print()
    if broken:
        print("%d of %d trials did NOT run the task instance they were graded "
              "against; their verdicts are not measurements of those instances."
              % (len(broken), len(rows)))
        print("AFFECTED: %s" % ", ".join("%s/%s" % (r["arm"], r["trial"])
                                         for r in broken))
    else:
        print("All trials ran their declared instances.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
