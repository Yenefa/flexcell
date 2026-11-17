"""Tests for the #253 hold-out gate.

The rule under test is not "the code stores a hash". It is "a result that could
have influenced the choice of candidate cannot be recorded as if it did not".
"""
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from holdout import (Freeze, HoldoutError, HoldoutPlan,  # noqa: E402
                     NOT_RUN, assert_frozen)

SHA = "a" * 40


def a_freeze(**over):
    kwargs = dict(candidate_sha=SHA, source_run_id="RUN-0010",
                  selection_basis="highest pre-registered criterion, chosen "
                                  "before any retained scenario ran",
                  frozen_at=time.time(), repair_runs=24)
    kwargs.update(over)
    return Freeze(**kwargs)


def a_plan(freeze=None):
    return HoldoutPlan(("layout_x", "layout_y"), ("s1", "s2", "s3"),
                       freeze or a_freeze())


# --------------------------------------------------------------- the gate
def test_a_candidate_that_was_never_frozen_is_refused():
    with pytest.raises(HoldoutError):
        assert_frozen(None, SHA)


def test_a_different_candidate_is_refused_even_with_a_valid_freeze():
    with pytest.raises(HoldoutError):
        assert_frozen(a_freeze(), "b" * 40)


def test_the_frozen_candidate_passes():
    assert assert_frozen(a_freeze(), SHA) is True


# ------------------------------------------------------------- the plan
def test_the_plan_is_the_six_slots_the_protocol_fixes():
    plan = a_plan()
    assert len(plan.slot_ids) == 6
    assert set(plan.statuses().values()) == {NOT_RUN}


def test_a_plan_needs_a_freeze_not_a_candidate_on_trust():
    with pytest.raises(HoldoutError):
        HoldoutPlan(("x", "y"), ("s1", "s2", "s3"), None)


def test_the_plan_refuses_a_different_shape_than_the_protocol():
    with pytest.raises(HoldoutError):
        HoldoutPlan(("x",), ("s1", "s2", "s3"), a_freeze())
    with pytest.raises(HoldoutError):
        HoldoutPlan(("x", "y"), ("s1",), a_freeze())


def test_repair_runs_and_holdout_runs_are_reported_separately():
    plan = a_plan(a_freeze(repair_runs=24))
    plan.record("layout_x|s1", "PASS", evaluated_sha=SHA)
    counts = plan.counts()
    assert counts["repair_runs"] == 24
    assert counts["holdout_executions"] == 1
    assert counts["holdout_planned"] == 6


# ------------------------------------------------- the rule that matters
def test_a_result_recorded_before_the_freeze_is_refused():
    """The whole point: a result that predates the freeze could have picked it."""
    freeze = a_freeze(frozen_at=time.time() + 60)     # freeze is in the future
    plan = a_plan(freeze)
    with pytest.raises(HoldoutError) as exc:
        plan.record("layout_x|s1", "PASS", evaluated_sha=SHA)
    assert "before the candidate was frozen" in str(exc.value)


def test_a_result_cannot_be_overwritten():
    plan = a_plan()
    plan.record("layout_x|s1", "FAIL", evaluated_sha=SHA)
    with pytest.raises(HoldoutError) as exc:
        plan.record("layout_x|s1", "PASS", evaluated_sha=SHA)
    assert "already recorded as FAIL" in str(exc.value)
    # and the failure is still what the report says
    assert plan.statuses()["layout_x|s1"] == "FAIL"


def test_each_slot_is_evaluated_against_the_frozen_candidate_only():
    plan = a_plan()
    with pytest.raises(HoldoutError):
        plan.record("layout_x|s1", "PASS", evaluated_sha="c" * 40)


def test_an_unknown_slot_is_refused():
    plan = a_plan()
    with pytest.raises(HoldoutError):
        plan.record("layout_z|s9", "PASS", evaluated_sha=SHA)


def test_an_outcome_outside_the_allowed_set_is_refused():
    plan = a_plan()
    for bad in ("PASSED", "ok", "pass", "UNKNOWN", ""):
        with pytest.raises(HoldoutError):
            plan.record("layout_x|s1", bad, evaluated_sha=SHA)


# ------------------------------------------------------------- reporting
def test_an_incomplete_plan_says_so_and_keeps_the_missing_slots_not_run():
    plan = a_plan()
    plan.record("layout_x|s1", "FAIL", evaluated_sha=SHA)
    report = plan.report()
    assert report["all_terminal"] is False
    assert report["slots"]["layout_y|s3"] == NOT_RUN
    # a failure is preserved, not dropped from the report
    assert report["slots"]["layout_x|s1"] == "FAIL"


def test_the_report_binds_the_freeze_so_it_cannot_be_swapped_afterwards():
    plan = a_plan()
    report = plan.report()
    assert report["freeze_sha"] == plan.freeze.sha()
    other = a_plan(a_freeze(selection_basis="picked the nicest looking one"))
    assert other.report()["freeze_sha"] != report["freeze_sha"]


def test_selection_basis_must_be_recorded_not_implied():
    for bad in ("", "   ", None, 7):
        with pytest.raises(HoldoutError):
            a_freeze(selection_basis=bad)
