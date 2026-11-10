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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import baseline_a_composite as ba

MAX_STAGES = 8


def build_plan(spec, clearance_m=0.06, tolerance_m=0.02):
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
