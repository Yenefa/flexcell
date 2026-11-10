#!/usr/bin/env python3
"""Record what each arm can plan for a given instance, without moving the robot.

This separates PLANNING from EXECUTION. A task can fail because the planner could not
produce a plan, or because the robot could not carry it out; conflating those two
would let me blame the robot for a planning gap and vice versa.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "experiments" / "baselines"))
sys.path.insert(0, str(WT / "runtime" / "planner"))

import baseline_a_prime_rules as apr

COLORS = {"target_box_a": "red", "target_box_b": "blue", "target_box_c": "green"}


def observation(spec):
    return {
        "instruction": spec["instruction"],
        "objects": [{"name": o["name"], "color": COLORS[o["name"]],
                     "position": list(o["initial_pose"][:3])} for o in spec["objects"]],
        "zones": [{"name": z["name"], "position": z["pose"], "radius": z["radius"]}
                  for z in spec["zones"]],
        "skills": ["observe", "pick", "place", "verify", "run_composite"],
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    obs = observation(spec)
    out = {"task_id": spec["task_id"], "arm": "A_prime_rules"}
    try:
        result = apr.plan(obs)
        out["planned"] = True
        out["rule"] = result.get("rule")
        out["mapping"] = {m["object"]: m["zone"] for m in result["moves"]}
    except apr.Unparsed as exc:
        out["planned"] = False
        out["refusal"] = str(exc)
    Path(argv[1]).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["planned"] else 1


if __name__ == "__main__":
    sys.exit(main())
