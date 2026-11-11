#!/usr/bin/env python3
"""Tests for the task-level false-failure metric.

FALSE FAILURE is the mirror of false success: the task reports failure while the independent
evaluator says the goal was satisfied. It was never measured before, and when it was, at
least 2 of 32 runs had it - each of which triggered a recovery retry of work already done.

The metric must read the two facts from their own artefacts: what the FSM concluded lives in
task.out, what the world looked like lives in the evaluator verdict. Reading one of them for
both would make the comparison vacuous.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ffr", ROOT / "experiments" / "baselines" / "false_failure_rate.py")
FFR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FFR)


def test_task_failure_is_read_from_task_out_not_from_the_verdict(tmp_path):
    d = tmp_path / "HO-x"
    d.mkdir()
    # the FSM said failure...
    (d / "task.out").write_text(
        'noise\nRESULT {"outcome": 1, "detail": "unconfirmed"}\n', encoding="utf-8")
    # ...while the evaluator said the goal was met
    (d / "verdict_after1.json").write_text('{"passed": true}', encoding="utf-8")
    assert FFR.task_reported_failure(str(d)) is True


def test_a_successful_task_reads_as_not_failed(tmp_path):
    d = tmp_path / "HO-y"
    d.mkdir()
    (d / "task.out").write_text('RESULT {"outcome": 0}\n', encoding="utf-8")
    assert FFR.task_reported_failure(str(d)) is False


def test_a_missing_task_out_yields_unknown_not_failure(tmp_path):
    """Unknown must never be silently read as a failure claim - that is the defect that made
    false success vacuous for many rounds in the other direction."""
    d = tmp_path / "HO-z"
    d.mkdir()
    (d / "task.out").write_text("no result line at all\n", encoding="utf-8")
    assert FFR.task_reported_failure(str(d)) is None


def test_the_two_directions_are_distinct(tmp_path):
    """A run can be a false failure or a false success, never both."""
    for outcome, passed, is_ff, is_fs in ((1, True, True, False),
                                          (0, False, False, True),
                                          (0, True, False, False),
                                          (1, False, False, False)):
        d = tmp_path / ("HO-%d-%d" % (outcome, passed))
        d.mkdir()
        (d / "task.out").write_text('RESULT {"outcome": %d}\n' % outcome,
                                    encoding="utf-8")
        failed = FFR.task_reported_failure(str(d))
        assert (failed and passed) is is_ff
        assert ((not failed) and (not passed)) is is_fs


def test_the_preregistration_records_that_its_basis_changed():
    """A pre-registration whose factual premise was corrected must say so in place."""
    p = ROOT / "evolution" / "proposals" / "actuator_stall_preregistration.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert "superseded_basis" in doc, (
        "the actuator-stall prediction assumed all stalls were real release failures")
    sb = doc["superseded_basis"]
    assert "false failure" in sb["measured"].lower() or "false failure" in sb["why"].lower()
    assert "NOT APPROVED" in sb["status_of_this_preregistration"]
    assert "never used to manufacture" in sb["leakage"]
