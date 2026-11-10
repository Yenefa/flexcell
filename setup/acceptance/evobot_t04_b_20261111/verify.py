#!/usr/bin/env python3
"""T04: the agent resolves a geometric relation instead of a colour label.

First template where the agent cannot pattern-match a colour word: the instruction
declares the colours misleading and requires the block FURTHER from the robot base.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "benchmark" / "evaluators"))
import evaluate as ev


def main():
    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
    obs = json.loads((HERE / "observation.json").read_text(encoding="utf-8"))
    reply = json.loads((HERE / "agent_reply.json").read_text(encoding="utf-8"))
    clean = {k: v for k, v in obs.items() if not k.startswith("_")}

    verdict = ev.evaluate(spec, clean)
    assert verdict["passed"] is True, verdict["failed_clauses"]
    assert verdict["false_success"] is False

    # the agent chose by distance, and the distance relation it used is real
    moves = {m["object"]: m["zone"] for m in reply["agent_plan"]["moves"]}
    assert reply["problems"] == []
    dist = {o["name"]: math.hypot(o["initial_pose"][0], o["initial_pose"][1])
            for o in spec["objects"]}
    to_right = [n for n, z in moves.items() if z == "zone_1"]
    to_left = [n for n, z in moves.items() if z == "zone_2"]
    assert len(to_right) == 1 and len(to_left) == 1
    assert dist[to_right[0]] > dist[to_left[0]], (dist, moves)

    # it reasoned about distance rather than colour
    reasons = " ".join(m.get("why", "") for m in reply["agent_plan"]["moves"]).lower()
    assert "far" in reasons or "distance" in reasons, reasons

    print(json.dumps({
        "verdict": "EVOBOT_T04_GEOMETRIC_DISCRIMINATION_VERIFIED",
        "task_id": spec["task_id"],
        "instruction": spec["instruction"],
        "arm": "B_runtime_agent",
        "agent_mapping": moves,
        "distances_m": {k: round(v, 4) for k, v in dist.items()},
        "agent_reasons": [m.get("why") for m in reply["agent_plan"]["moves"]],
        "passed": True,
        "false_success": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
