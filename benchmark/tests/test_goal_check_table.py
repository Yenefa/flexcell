#!/usr/bin/env python3
"""Tests for the goal-check table: the LABEL must come from the decision, not from a file.

WHY: my first archival table labelled a run "SATISFIED" only because goal_check.json existed
and held a "stages" list. That run's decision was action=resume - the check had compared the
stages and found the goal NOT satisfied. Publishing that table would have mislabelled the one
case that proves the check is conservative.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "gct", ROOT / "experiments" / "baselines" / "goal_check_table.py")
GCT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GCT)


def _run(tmp_path, name, decision, goal_check=None, task_outcome=1, b=True, r=True):
    d = tmp_path / name
    d.mkdir()
    (d / "recovery_decision.json").write_text(json.dumps(decision), encoding="utf-8")
    if goal_check is not None:
        (d / "goal_check.json").write_text(json.dumps(goal_check), encoding="utf-8")
    (d / "task.out").write_text('RESULT {"outcome": %d}\n' % task_outcome,
                                encoding="utf-8")
    (d / "verdict_after1.json").write_text(json.dumps({"passed": b}), encoding="utf-8")
    (d / "verdict.json").write_text(json.dumps({"passed": r}), encoding="utf-8")
    return d


def test_a_skip_is_labelled_from_the_decision_reason(tmp_path):
    d = _run(tmp_path, "HO-a",
             {"action": "no_recovery", "reason": "goal already satisfied by measurement"},
             {"tolerance_m": 0.02,
              "stages": [{"object": "x", "distance_m": 0.005, "status": "AT_TARGET"}]})
    label, detail = GCT.classify(str(d))
    assert label.startswith("SKIPPED"), label
    assert "5.0mm" in detail


def test_a_stages_file_with_a_resume_decision_is_not_satisfied(tmp_path):
    """This is the exact mislabel that was caught: stages present, goal NOT met."""
    d = _run(tmp_path, "HO-b",
             {"action": "resume", "why": "measured state no longer matches"},
             {"tolerance_m": 0.02,
              "stages": [{"object": "y", "distance_m": 0.5,
                          "status": "OUTSIDE_TOLERANCE"}]})
    label, detail = GCT.classify(str(d))
    assert label == "checked, NOT met", label
    assert "OUTSIDE_TOLERANCE" in detail


def test_a_refusal_is_labelled_refused(tmp_path):
    d = _run(tmp_path, "HO-c",
             {"action": "resume"},
             {"decision": "REFUSED - fall through", "repeated_objects": ["z"]})
    label, detail = GCT.classify(str(d))
    assert label.startswith("REFUSED"), label
    assert "z" in detail


def test_a_successful_task_is_not_consulted(tmp_path):
    d = _run(tmp_path, "HO-d", {"action": "no_recovery",
                                "reason": "first attempt succeeded"}, task_outcome=0)
    label, _ = GCT.classify(str(d))
    assert label == "not consulted"


def test_the_real_batch_has_exactly_the_expected_split():
    base = Path("/tmp/evobot-batch3")
    if not base.is_dir():
        return
    labels = [GCT.classify(str(d))[0] for d in sorted(base.glob("HO-*"))]
    assert labels.count("SKIPPED (goal met)") == 3
    assert sum(1 for l in labels if l.startswith("REFUSED")) == 2
    assert labels.count("checked, NOT met") == 1
