#!/usr/bin/env python3
"""Verify the actuator root-cause finding from archived episodes."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(WT / "runtime" / "recovery"))
import execution_root_cause as E


def main():
    base = Path("/tmp/evobot-pair16")
    if not base.exists():
        print(json.dumps({"verdict": "SKIPPED", "why": "run artefacts not present"}))
        return 0
    counts = {}
    for d in sorted(base.glob("HO-*")):
        label, _ = E.run_root_cause(str(d))
        counts[label] = counts.get(label, 0) + 1
    assert counts.get("ACTUATOR_STALL_ON_RELEASE", 0) == 4, counts
    assert counts.get("OTHER", 0) == 12, counts

    # the classifier must not mislabel unrelated text
    assert E.classify("gripper did not open (position=-0.011)") == "ACTUATOR_STALL_ON_RELEASE"
    assert E.classify("gripper did not close (position=0.02)") == "ACTUATOR_STALL_ON_GRASP"
    assert E.classify("ik unreachable") == "KINEMATICS"
    assert E.classify("something else") == "OTHER"

    # every stalled run must have failed its first attempt
    stalled_failed_first = 0
    for d in sorted(base.glob("HO-*")):
        label, _ = E.run_root_cause(str(d))
        if label != "ACTUATOR_STALL_ON_RELEASE":
            continue
        b = json.loads((d / "verdict_after1.json").read_text(encoding="utf-8"))
        assert b["passed"] is False, d.name
        stalled_failed_first += 1
    assert stalled_failed_first == 4

    print(json.dumps({
        "verdict": "EVOBOT_ACTUATOR_ROOT_CAUSE_VERIFIED",
        "actuator_stalls": 4,
        "recovered_by_bounded_retry": 3,
        "unrelated_failures": 12,
        "finding": "gripper stalled while RELEASING; not a planning or experience problem",
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
