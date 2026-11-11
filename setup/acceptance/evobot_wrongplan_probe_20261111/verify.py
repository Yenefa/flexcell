#!/usr/bin/env python3
"""Verify the probe actually demonstrated a false success.

WHY EVERY ASSERTION HERE IS ABOUT THE SETUP: three earlier attempts failed to modify what they
were meant to modify, and one of them would have read as "the check is safe". A probe is only
evidence if it proves it ran the wrong plan, that the world followed it, that the evaluator
failed, and that the check still said success.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run_foreign_plan"


def main():
    plan = json.loads((RUN / "plan.json").read_text(encoding="utf-8"))
    gt = json.loads((RUN / "ground_truth.json").read_text(encoding="utf-8"))
    verdict = json.loads((RUN / "verdict.json").read_text(encoding="utf-8"))
    report = (HERE / "result.txt").read_text(encoding="utf-8")

    # 1. the executed plan is the donor's, and it targets the zone the task does NOT want
    targets = [(s["object_name"], [round(v, 3) for v in s["place_pose"][:2]])
               for s in plan["stages"]]
    assert targets == [("target_box_a", [0.075, -0.15]),
                       ("target_box_b", [0.165, -0.15])], targets

    # 2. the world actually moved and followed that plan (not left at the start poses)
    start = {"target_box_a": [0.22, 0.0], "target_box_b": [0.2, -0.18]}
    for name, pose in gt["objects"].items():
        moved = (round(pose[0], 2), round(pose[1], 2)) != tuple(start[name])
        assert moved, (name, "world did not move - the probe proved nothing")

    # 3. the evaluator failed
    assert verdict["passed"] is False, verdict
    assert "placement:target_box_a" in verdict.get("failed_clauses", []), verdict

    # 4. the check under test still said success
    assert "CLAIM CHECK   : True" in report, report[-600:]
    assert "EVALUATOR     : passed=False" in report, report[-600:]

    # 5. and the earlier attempts are on record
    attempts = (HERE / "attempts.txt").read_text(encoding="utf-8")
    assert attempts.count("v") >= 3
    assert "silently not applied" in attempts

    print(json.dumps({
        "verdict": "EVOBOT_FALSE_SUCCESS_DEMONSTRATED_BY_WRONG_PLAN",
        "setup": "donor plan for a zone_1 task executed on a zone_2 task",
        "world_followed_the_wrong_plan": True,
        "evaluator": "passed=False (placement + order)",
        "claim_check": "True - both conditions met",
        "meaning": ("the two-condition check verifies execution against the plan and cannot "
                    "see that the plan is wrong for the instruction"),
        "decision": "do not adopt it as the agent claim",
        "earlier_attempts_that_proved_nothing": 3,
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
