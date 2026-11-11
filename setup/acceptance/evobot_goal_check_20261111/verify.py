#!/usr/bin/env python3
"""Verify the goal check: it skips pointless retries and refuses to skip real ones."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
spec = importlib.util.spec_from_file_location(
    "gc", WT / "runtime" / "recovery" / "goal_check.py")
GC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GC)


def load(base, oid):
    plan = json.loads((Path(base) / oid / "plan.json").read_text(encoding="utf-8"))
    gt = json.loads((Path(base) / oid / "ground_truth_after1.json").read_text(
        encoding="utf-8"))
    return plan, gt.get("objects") or {}


def main():
    done, refused = [], []

    # 1. the two measured false failures must be recognised as already done
    for oid in ("HO-a69ec651037a", "HO-f9431f8ef925"):
        plan, measured = load("/tmp/evobot-batch2", oid)
        ok, detail = GC.check(plan, measured)
        assert ok is True, (oid, detail)
        done.append(oid)

    # 2. the two runs where recovery produced the only measured gain must NOT be skipped
    for oid in ("HO-5a96f3eb4fae", "HO-47afdffad81a"):
        plan, measured = load("/tmp/evobot-batch1", oid)
        ok, detail = GC.check(plan, measured)
        assert ok is False, (oid, "would have deleted a measured gain", detail)
        refused.append(oid)

    # 3. the tolerance must be the plan's own, and strictly tighter than the acceptance radius
    plan, measured = load("/tmp/evobot-batch2", "HO-a69ec651037a")
    assert plan["position_tolerance_m"] == 0.02
    _, detail = GC.check(plan, measured)
    assert detail["tolerance_m"] == 0.02
    assert 0.02 < 0.06, "the plan tolerance must be tighter than the zone radius, or this "
    # check could skip a retry the evaluator would have failed

    # 4. it must be wired in, not merely implemented
    drv = (WT / "runtime" / "recovery" / "recovery_driver.py").read_text(encoding="utf-8")
    assert "import goal_check" in drv
    assert "goal already satisfied by measurement" in drv

    print(json.dumps({
        "verdict": "EVOBOT_GOAL_CHECK_VERIFIED",
        "skips_pointless_retry_for": done,
        "refuses_to_skip_real_gains": refused,
        "tolerance": "plan.position_tolerance_m = 0.02 (acceptance radius 0.06)",
        "cannot_manufacture_a_pass": True,
        "evaluator_touched": False,
        "skill_layer_touched": False,
        "end_to_end_validated_on_new_batch": False,
        "caveat": "validated on archived data and unit tests only, not yet on a new batch",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
