#!/usr/bin/env python3
"""Tests for goal_check: skip a pointless retry, but never skip a needed one.

WHY THIS EXISTS: the recovery driver triggers off task.out, and that conclusion can be a
false negative. Over 32 validated runs, 2 had the task report failure while the box was
already released and inside the target zone. Recovery retried a finished placement.

WHY EVERY TEST BELOW IS ABOUT REFUSING, NOT ABOUT ACCEPTING: accepting is the dangerous
direction. A check that wrongly says "already done" ends a run early; if it is too eager it
silently drops the recovery gains that are this project's only measured improvement. So the
accepting cases are pinned to REAL archived data, and the refusing cases are pinned to real
runs whose recovery is known to have produced a gain.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "gc", ROOT / "runtime" / "recovery" / "goal_check.py")
GC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GC)

BATCH1 = Path("/tmp/evobot-batch1")
BATCH2 = Path("/tmp/evobot-batch2")


def _load(base, oid):
    plan = json.loads((base / oid / "plan.json").read_text(encoding="utf-8"))
    gt = json.loads((base / oid / "ground_truth_after1.json").read_text(encoding="utf-8"))
    return plan, gt.get("objects") or {}


def test_a_satisfied_single_stage_plan_is_detected():
    plan = {"position_tolerance_m": 0.02,
            "stages": [{"stage_id": "a-0", "object_name": "a",
                        "place_pose": [0.1, 0.0, 0.0]}]}
    ok, detail = GC.check(plan, {"a": [0.105, 0.005, 0.0]})
    assert ok is True
    assert detail["stages"][0]["status"] == "AT_TARGET"


def test_an_object_outside_tolerance_blocks_the_conclusion():
    plan = {"position_tolerance_m": 0.02,
            "stages": [{"stage_id": "a-0", "object_name": "a",
                        "place_pose": [0.1, 0.0, 0.0]}]}
    ok, detail = GC.check(plan, {"a": [0.2, 0.0, 0.0]})
    assert ok is False
    assert detail["stages"][0]["status"] == "OUTSIDE_TOLERANCE"


def test_a_missing_measurement_blocks_the_conclusion():
    plan = {"position_tolerance_m": 0.02,
            "stages": [{"stage_id": "a-0", "object_name": "a",
                        "place_pose": [0.1, 0.0, 0.0]}]}
    ok, detail = GC.check(plan, {})
    assert ok is False
    assert detail["stages"][0]["status"] == "NOT_MEASURED"


def test_a_multi_stage_object_is_refused_outright():
    """A T12 triple revisit lists the same object three times. Sitting on the FIRST target is
    not completion, and final position alone cannot prove the ORDER was met either."""
    plan = {"position_tolerance_m": 0.02,
            "stages": [{"stage_id": "a-0", "object_name": "a", "place_pose": [0.12, -0.195, 0]},
                       {"stage_id": "a-1", "object_name": "a", "place_pose": [0.25, 0.05, 0]},
                       {"stage_id": "a-2", "object_name": "a", "place_pose": [0.12, -0.105, 0]}]}
    ok, detail = GC.check(plan, {"a": [0.12, -0.195, 0]})
    assert ok is False
    assert detail["repeated_objects"] == ["a"]
    assert "REFUSED" in detail["decision"]


def test_a_plan_without_a_declared_tolerance_is_refused():
    plan = {"stages": [{"stage_id": "a-0", "object_name": "a", "place_pose": [0.1, 0, 0]}]}
    ok, detail = GC.check(plan, {"a": [0.1, 0, 0]})
    assert ok is False
    assert "refusing to guess" in detail["why"]


def test_the_real_false_failures_are_recognised_as_already_done():
    """These two runs had recovery retry a placement that was already complete."""
    if not BATCH2.is_dir():
        return
    for oid in ("HO-a69ec651037a", "HO-f9431f8ef925"):
        plan, measured = _load(BATCH2, oid)
        ok, detail = GC.check(plan, measured)
        assert ok is True, (oid, detail)
        assert all(s["status"] == "AT_TARGET" for s in detail["stages"]), detail


def test_the_real_gains_are_never_skipped():
    """HO-5a96f3eb4fae and HO-47afdffad81a are the two runs where recovery turned a failure
    into a pass. If this check said "already done" for either, it would delete the measured
    gain - so it must refuse."""
    if not BATCH1.is_dir():
        return
    for oid in ("HO-5a96f3eb4fae", "HO-47afdffad81a"):
        plan, measured = _load(BATCH1, oid)
        ok, detail = GC.check(plan, measured)
        assert ok is False, (oid, "this check must not skip a real recovery gain", detail)


def test_the_tolerance_comes_from_the_plan_not_the_evaluator():
    """Proven by DEPENDENCE and by BEHAVIOUR, not by scanning prose.

    The module must not import the evaluator or anything that can read the held-out answer,
    and it must use the plan's declared tolerance even when the caller supplies no value.
    """
    src = (ROOT / "runtime" / "recovery" / "goal_check.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines()
                      if l.strip() and not l.strip().startswith("#"))
    assert "position_tolerance_m" in code
    assert "import" in code
    for forbidden in ("evaluate", "sealed_evaluate", "held_out"):
        assert ("import " + forbidden) not in code, forbidden
        assert ("from " + forbidden) not in code, forbidden
    plan = {"position_tolerance_m": 0.02,
            "stages": [{"stage_id": "a-0", "object_name": "a", "place_pose": [0.1, 0, 0]}]}
    _, detail = GC.check(plan, {"a": [0.1, 0, 0]})
    assert detail["tolerance_m"] == 0.02
