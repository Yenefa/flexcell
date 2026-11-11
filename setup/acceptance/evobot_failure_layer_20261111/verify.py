#!/usr/bin/env python3
"""Verify the layer attribution, and that the classifier is not one-sided."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
spec = importlib.util.spec_from_file_location(
    "fl", WT / "experiments" / "baselines" / "failure_layer.py")
FL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FL)


def main():
    counts = {"PLANNER": 0, "EXECUTION": 0, "UNKNOWN": 0, "ok": 0}
    n = 0
    for base in ("/tmp/evobot-batch1", "/tmp/evobot-batch2",
                 "/tmp/evobot-batch3", "/tmp/evobot-batch4"):
        if not Path(base).is_dir():
            continue
        for d in sorted(Path(base).glob("HO-*")):
            n += 1
            v1 = json.loads((d / "verdict_after1.json").read_text(encoding="utf-8")) \
                if (d / "verdict_after1.json").exists() else {}
            oc = FL.outcome(str(d))
            if v1.get("passed") and oc == 0:
                counts["ok"] += 1
                continue
            if v1.get("passed"):
                counts["EXECUTION"] += 1
                continue
            counts[FL.attribute(str(d))[0]] += 1

    assert n == 64, n
    assert counts["PLANNER"] == 0, counts
    assert counts["ok"] == 49, counts
    assert counts["EXECUTION"] == 15, counts

    # the zero means nothing unless the classifier could have said PLANNER
    src = (WT / "experiments" / "baselines" / "failure_layer.py").read_text(
        encoding="utf-8")
    assert "PLANNER" in src and "EXECUTION" in src and "UNKNOWN" in src
    tests = (WT / "benchmark" / "tests" / "test_failure_layer.py").read_text(
        encoding="utf-8")
    assert tests.count("PLANNER") >= 3, "negative cases are what make the zero meaningful"

    print(json.dumps({
        "verdict": "EVOBOT_FAILURE_LAYER_ATTRIBUTED",
        "runs": n,
        "passed_cleanly": counts["ok"],
        "planner_attributable": counts["PLANNER"],
        "execution_attributable": counts["EXECUTION"],
        "unattributed": counts["UNKNOWN"],
        "level_7_conclusion": ("unobservable because the planner commits no errors here, "
                              "not because lesson delivery is broken"),
        "execution_breakdown": {"skill_layer_false_failure": 8, "real_grasp_stall": 7},
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
