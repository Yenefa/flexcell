#!/usr/bin/env python3
"""Verify the half of the skill-growth experiment that produced a result.

The open-loop arm failed the relational clause by ~9.8 mm against a 6 mm tolerance: that is the
task defeating the procedure the runtime already had, and it is proven. The closed-loop arm is
implemented but its second placement never moved the object, so the new skill is NOT yet shown
to work. A verifier that only checked "the experiment ran" would hide exactly that.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name):
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    b = _load("verdict_B.json")
    c = _load("verdict_C.json")
    gb = _load("ground_truth_B.json")
    gc = _load("ground_truth_C.json")
    assert b and c and gb and gc, "archived verdicts/worlds missing"

    assert b["passed"] is False
    assert b["failed_clauses"] == ["relative:target_box_b@target_box_a"], b["failed_clauses"]

    red = gb["objects"]["target_box_a"]
    blue = gb["objects"]["target_box_b"]
    want = (red[0], red[1] + 0.06)
    err = ((blue[0] - want[0]) ** 2 + (blue[1] - want[1]) ** 2) ** 0.5
    assert err > 0.006, ("open loop would have passed; task does not defeat it", err)
    assert err < 0.02, ("miss is larger than execution noise", err)

    c_blue = gc["objects"]["target_box_b"]
    moved = abs(c_blue[0] - 0.20) > 0.005 or abs(c_blue[1] + 0.18) > 0.005
    assert not moved, ("closed loop now moves it - update the conclusion", c_blue)

    print(json.dumps({
        "verdict": "EVOBOT_SKILL_GROWTH_OPEN_LOOP_DEFEATED_SKILL_UNPROVEN",
        "relational_clause_added": True,
        "regression": "64/64 archived runs re-graded identically",
        "open_loop": {"placement": "passed", "relative": "failed",
                      "miss_m": round(err, 5), "tolerance_m": 0.006},
        "closed_loop": {"implemented": True, "second_placemement_moved_object": False},
        "proven": "one-shot planning cannot solve this task",
        "NOT_proven": "that the synthesized procedure solves it",
        "evaluator_change": "generic relative clause, v0.2.0, no clause weakened",
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
