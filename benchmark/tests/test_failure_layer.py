#!/usr/bin/env python3
"""Tests for failure-layer attribution.

WHY THE NEGATIVE CASES MATTER MOST: the headline result is "0 of 64 failures are
planner-attributable", and a classifier that can only ever output EXECUTION would produce that
number without meaning anything. So every test below that is not the headline is a case where the
classifier MUST say PLANNER. If those start failing, the zero is not evidence of anything.

The distinction being measured decides what to build next: a planner-attributable failure means
better planning or better lessons; an execution-attributable one means the planner is fine and the
effort belongs below it.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "fl", ROOT / "experiments" / "baselines" / "failure_layer.py")
FL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FL)


def _run(tmp_path, files, name="HO-x"):
    d = tmp_path / name
    d.mkdir()
    for name, content in files.items():
        (d / name).write_text(json.dumps(content), encoding="utf-8")
    return str(d)


def test_a_missing_plan_is_a_planner_failure(tmp_path):
    d = _run(tmp_path, {"task.out": {"RESULT ": 1}})
    layer, why = FL.attribute(d)
    assert layer == "PLANNER"
    assert "no plan" in why


def test_a_declared_plan_defect_is_a_planner_failure(tmp_path):
    d = _run(tmp_path, {
        "plan.json": {"stages": []},
        "failure_evidence.json": {
            "detail": "plan must declare every observed object"},
    })
    assert FL.attribute(d)[0] == "PLANNER"


def test_an_unparseable_reply_is_a_planner_failure(tmp_path):
    d = _run(tmp_path, {
        "plan.json": {"stages": []},
        "failure_evidence.json": {"detail": "no JSON in reply"},
    })
    assert FL.attribute(d)[0] == "PLANNER"


def test_a_skill_stall_is_an_execution_failure(tmp_path):
    d = _run(tmp_path, {
        "plan.json": {"stages": [{"object_name": "a"}]},
        "failure_evidence.json": {"detail": "native place stage failed: PLACE_A:FAIL"},
        "recovery_decision.json": {"decision": {"failure_class": "grasp"}},
    })
    layer, why = FL.attribute(d)
    assert layer == "EXECUTION"
    assert why == "grasp"


def test_an_empty_evidence_file_is_unknown_not_execution(tmp_path):
    """Unknown must not be laundered into EXECUTION, or the zero becomes vacuous."""
    d = _run(tmp_path, {"plan.json": {"stages": []}}, name="HO-empty")
    assert FL.attribute(d)[0] == "UNKNOWN", ("no evidence must not become EXECUTION")
    d2 = _run(tmp_path, {"plan.json": {"stages": []},
                         "failure_evidence.json": {"detail": ""}}, name="HO-blank")
    assert FL.attribute(d2)[0] == "UNKNOWN"


def test_the_classifier_can_emit_every_layer():
    """If PLANNER were unreachable the headline zero would be an artefact."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        seen = set()
        (p / "a").mkdir()
        (p / "a" / "task.out").write_text('RESULT {"outcome": 1}\n', encoding="utf-8")
        seen.add(FL.attribute(str(p / "a"))[0])
        (p / "b").mkdir()
        (p / "b" / "plan.json").write_text('{"stages": []}', encoding="utf-8")
        (p / "b" / "failure_evidence.json").write_text('{"detail": ""}', encoding="utf-8")
        seen.add(FL.attribute(str(p / "b"))[0])
        (p / "c").mkdir()
        (p / "c" / "plan.json").write_text('{"stages": []}', encoding="utf-8")
        (p / "c" / "failure_evidence.json").write_text(
            '{"detail": "gripper stalled"}', encoding="utf-8")
        seen.add(FL.attribute(str(p / "c"))[0])
        assert seen == {"PLANNER", "UNKNOWN", "EXECUTION"}, seen


def test_the_archived_batches_contain_no_planner_attributable_failure():
    n = 0
    for base in ("/tmp/evobot-batch1", "/tmp/evobot-batch2",
                 "/tmp/evobot-batch3", "/tmp/evobot-batch4"):
        if not Path(base).is_dir():
            continue
        for d in sorted(Path(base).glob("HO-*")):
            n += 1
            v1 = json.loads((d / "verdict_after1.json").read_text(encoding="utf-8")) \
                if (d / "verdict_after1.json").exists() else {}
            if v1.get("passed") and FL.outcome(str(d)) == 0:
                continue
            if v1.get("passed"):
                continue
            layer, why = FL.attribute(str(d))
            assert layer != "PLANNER", (d.name, why)
    if n:
        assert n == 64, n
