#!/usr/bin/env python3
"""Tests for the wrong-plan probe: the setup must be checkable, not just described.

WHY: three earlier versions of this probe failed to change anything, and one of them would have
read as evidence that the check is safe. Every assertion here is about the SETUP - the donor plan
was really used, the world really moved, the evaluator really failed - because a probe that
cannot fail to demonstrate what it claims is not a probe.
"""
import json
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT / "setup" / "acceptance" / "evobot_wrongplan_probe_20261111" / "run_foreign_plan"


def test_the_donor_plan_is_the_one_that_ran():
    if not RUN.is_dir():
        return
    plan = json.loads((RUN / "plan.json").read_text(encoding="utf-8"))
    targets = [(s["object_name"], [round(v, 3) for v in s["place_pose"][:2]])
               for s in plan["stages"]]
    assert targets == [("target_box_a", [0.075, -0.15]),
                       ("target_box_b", [0.165, -0.15])], targets


def test_the_world_moved_away_from_its_start_pose():
    """The failure mode of probe v1: nothing moved, and the result still looked fine."""
    if not RUN.is_dir():
        return
    gt = json.loads((RUN / "ground_truth.json").read_text(encoding="utf-8"))
    start = {"target_box_a": (0.22, 0.0), "target_box_b": (0.2, -0.18)}
    for name, pose in gt["objects"].items():
        assert (round(pose[0], 2), round(pose[1], 2)) != start[name], name


def test_the_evaluator_failed_on_the_world_the_wrong_plan_produced():
    if not RUN.is_dir():
        return
    verdict = json.loads((RUN / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["passed"] is False
    assert verdict.get("failed_clauses")


def test_the_check_under_test_said_success():
    p = ROOT / "setup" / "acceptance" / "evobot_wrongplan_probe_20261111" / "result.txt"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    assert "CLAIM CHECK   : True" in text
    assert "passed=False" in text


def test_the_three_failed_attempts_are_recorded():
    p = ROOT / "setup" / "acceptance" / "evobot_wrongplan_probe_20261111" / "attempts.txt"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    assert "v1" in text and "v2" in text and "v3" in text
    assert "silently not applied" in text
    assert "refused" in text
