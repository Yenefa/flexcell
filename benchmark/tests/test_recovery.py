#!/usr/bin/env python3
"""Tests for Level 3 recovery: bounded, pre-registered, never weakens grading."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "recovery"))
import recover

Z1 = [0.12, -0.15, 0.0175]


def test_action_table_is_fixed_and_covers_every_class():
    sys.path.insert(0, str(ROOT / "evolution" / "experience"))
    import store
    assert set(recover.ACTION_TABLE) == set(store.FAILURE_CLASSES), (
        set(store.FAILURE_CLASSES) - set(recover.ACTION_TABLE))


def test_planning_failure_gets_a_bounded_respread():
    d = recover.decide({"detail": "declared destination occupied at a-1"})
    assert d["failure_class"] == "planning" and d["action"] == "respread"
    assert d["budget"] == 1


def test_retry_budget_is_enforced():
    d = recover.decide({"detail": "declared destination occupied"}, attempt=2)
    assert d["action"] == "no_recovery"
    assert "budget" in d["reason"]


def test_unknown_failure_is_not_guessed_at():
    d = recover.decide({"detail": "something odd happened"})
    assert d["failure_class"] == "UNKNOWN" and d["action"] == "no_recovery"


def test_respread_widens_same_bin_destinations_within_the_radius():
    plan = {"stages": [{"object_name": "a", "place_pose": list(Z1)},
                       {"object_name": "b", "place_pose": list(Z1)}]}
    out = recover.apply_respread(plan)
    p0, p1 = out["stages"][0]["place_pose"], out["stages"][1]["place_pose"]
    assert p0 != p1
    sep = abs(p0[0] - p1[0])
    assert sep > 0.056, sep
    assert abs(p0[0] - Z1[0]) <= 0.06 and abs(p1[0] - Z1[0]) <= 0.06
    assert out["recovered"] is True


def test_respread_does_not_mutate_the_original_plan():
    import json
    plan = {"stages": [{"object_name": "a", "place_pose": list(Z1)},
                       {"object_name": "b", "place_pose": list(Z1)}]}
    before = json.dumps(plan, sort_keys=True)
    recover.apply_respread(plan)
    assert json.dumps(plan, sort_keys=True) == before


def test_respread_refuses_to_leave_the_bin():
    plan = {"stages": [{"object_name": n, "place_pose": list(Z1)} for n in "abc"]}
    with pytest.raises(ValueError):
        recover.apply_respread(plan, spread_step=0.09)


def test_respread_never_changes_zones_or_grading_keys():
    plan = {"stages": [{"object_name": "a", "place_pose": list(Z1)}],
            "clearance_m": 0.05, "position_tolerance_m": 0.02}
    out = recover.apply_respread(plan)
    assert out["clearance_m"] == plan["clearance_m"]
    assert out["position_tolerance_m"] == plan["position_tolerance_m"]
    assert "evaluator" not in json.dumps(out).lower()


def test_record_preserves_the_original_failure():
    ev = {"error_code": 61, "detail": "occupied destination"}
    d = recover.decide(ev)
    r = recover.record(ev, d, "run-x")
    assert r["original_evidence"] == ev and r["original_failure_preserved"] is True

