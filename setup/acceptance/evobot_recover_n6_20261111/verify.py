#!/usr/bin/env python3
"""Verify the Level 3 recovery experiment is genuine."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    rec = RUNS / "HO-b81a5ae02d6d"
    d = load(rec / "recovery_decision.json")
    assert d["decision"]["action"] == "resume"
    assert d["decision"]["committed_stages"] == ["target_box_a-0"]
    # the retry plan must drop committed stages and use MEASURED positions
    p1 = load(rec / "plan.json")
    p2 = load(rec / "plan_retry.json")
    assert len(p2["stages"]) < len(p1["stages"])
    assert p2["resumed_from_stage_ids"] == ["target_box_a-0"]
    assert p2["initial_objects"] != p1["initial_objects"]
    # grading contract untouched
    assert p2["clearance_m"] == p1["clearance_m"]
    assert p2["position_tolerance_m"] == p1["position_tolerance_m"]
    # first attempt failed, second succeeded, independent evaluation passed
    a1 = load(rec / "failure_evidence.json")
    assert a1["outcome"] != 0
    v = load(rec / "verdict.json")
    assert v["passed"] is True and v["false_success"] is False

    # the failure case must stay a failure, not be papered over
    bad = RUNS / "HO-90899d657e68" / "verdict.json"
    assert load(bad)["passed"] is False

    # false success across the batch
    total, fs = 0, 0
    for vp in RUNS.glob("*/verdict.json"):
        total += 1
        fs += 1 if load(vp).get("false_success") else 0
    assert fs == 0, fs
    print(json.dumps({"verdict": "EVOBOT_LEVEL3_RECOVERY_VERIFIED",
                      "recovery_rate": "1/2",
                      "grading_unchanged": True,
                      "false_success_rate": 0.0,
                      "graded_runs": total}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
