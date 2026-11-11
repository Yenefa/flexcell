#!/usr/bin/env python3
"""Verify the first OFFICIAL external-benchmark task actually completed.

The claim is deliberately narrow: LIBERO's own task, LIBERO's own environment, LIBERO's own
predicate, True. It says nothing about EvoBot's planner - a scripted phase controller produced it.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    r = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    assert r["official_success"] is True, r["official_success"]
    assert r["phase_success"] is True
    trace = [l for l in r["log"] if "settle trace" in l]
    assert trace and '"success": true' in trace[0], trace[:1]
    final = [l for l in r["log"] if "object final at" in l][0]
    xy = final.split("[")[1].split("]")[0].split(",")
    assert abs(float(xy[0]) - (-0.12)) > 0.05, ("object did not move", final)
    assert abs(float(xy[1]) - (-0.24)) > 0.05, ("object did not move", final)

    calib = json.loads((HERE / "calibration.json").read_text(encoding="utf-8"))
    good = [c["descend_target"] for c in calib if c.get("carried")]
    assert good, "no working grasp height recorded"
    assert any(c.get("lift_above_control", 0) > 0.05 for c in calib), calib

    print(json.dumps({
        "verdict": "EVOBOT_OFFICIAL_EXTERNAL_TASK_COMPLETED",
        "benchmark": "LIBERO",
        "classification": {"official": True, "adapted": False, "native": False},
        "task": r["task"],
        "official_success": True,
        "object_moved_across_the_table": True,
        "grasp_heights_that_work": good,
        "root_causes_found_by_experiment": [
            "gripper sign convention (+1 closes, not opens)",
            "aimed at basket body z=0.035 instead of the official contain region z=0.1068",
        ],
        "policy": "scripted phase controller - NOT an LLM planner result",
        "perception": "ORACLE",
        "evobot_gazebo_stack_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
