#!/usr/bin/env python3
"""Verify what the adapter achieved and, just as importantly, what it did not."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    r = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    assert r["official_success"] is False
    assert r["phase_success"] is True          # not a pipeline failure
    final = r["log"][-1]
    assert "never left its start pose" in final, final
    rp = r["reach_probe"]
    assert rp["lowest_eef_z_in_free_space"] <= 0.03, rp
    assert "reach is fine" in rp["reading"], rp
    assert "ORACLE" in r["perception"]
    print(json.dumps({
        "verdict": "EVOBOT_LIBERO_ADAPTER_RUNS_GRASP_FAILS",
        "official_task": r["task"],
        "phases_completed": True,
        "object_moved": False,
        "official_success": False,
        "root_cause": "fingers stop on the can lid; reach in free space is 0.02 m, so the arm is capable",
        "perception": "ORACLE - execution result, not a perception result",
        "classification": {"official": True, "adapted": False, "native": False},
        "evobot_gazebo_stack_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
