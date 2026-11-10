#!/usr/bin/env python3
"""Turn a TaskSpec into the concrete RunComposite plan Baseline A will dispatch.

This is the glue between the benchmark (which speaks TaskSpec) and the robot (which
speaks RunComposite). It is mechanical: stage order and destinations come straight
from the spec, and initial_objects are the declared start poses.

It refuses to build a plan it cannot justify rather than guessing:
  - a template whose stages exceed RunComposite's 8-stage bound is rejected;
  - a relay plan that would need the same bin twice is rejected.
"""
import json
import sys

# Occupancy clearance for the plan declaration.
#
# It was hardcoded to 0.060 (copied from the server config default) and never checked
# against the scene. It turned out to be 1.7 mm too large: box_a spawns 58.3 mm from
# zone_2 centre, so any task placing into zone_2 while box_a stays put was declared
# infeasible. Two 35 mm boxes only need centre separation above 35 mm to avoid
# overlap, so 1.3x the box edge is physically justified and no longer contradicts the
# scene. This is the PLANNER occupancy declaration - the evaluator acceptance radius
# (0.06 m) is untouched.
CLEARANCE_FACTOR = 1.3

# The RunComposite contract accepts clearance_m only in 0.05..0.25, so the derived
# value is clamped into that window. For 35 mm boxes 1.3x edge is 45.5 mm, which is
# below the contract floor, so the floor is what actually applies.
CLEARANCE_MIN = 0.05
CLEARANCE_MAX = 0.25
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import baseline_a_composite as ba

MAX_STAGES = 8


def build_plan(spec, clearance_m=None, tolerance_m=0.02):
    if clearance_m is None:
        edge = spec["objects"][0]["size"][0]
        clearance_m = min(CLEARANCE_MAX, max(CLEARANCE_MIN, round(CLEARANCE_FACTOR * edge, 4)))
    stages = ba.plan_from_spec(spec)
    if not stages:
        raise ValueError("template produced no stages")
    if len(stages) > MAX_STAGES:
        raise ValueError("plan needs %d stages, RunComposite allows %d"
                         % (len(stages), MAX_STAGES))
    initial = [{"object_name": o["name"], "position": list(o["initial_pose"][:3])}
               for o in spec["objects"]]
    return {
        "task_id": spec["task_id"],
        "initial_objects": initial,
        "stages": stages,
        "final_empty_positions": [],
        "position_tolerance_m": tolerance_m,
        "clearance_m": clearance_m,
        "motion_profile_id": "demo_slow",
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: build_composite_plan.py <spec.json> <out.json>", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    plan = build_plan(spec)
    Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(argv[1]).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print("plan: %d stages for %s" % (len(plan["stages"]), plan["task_id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
