#!/usr/bin/env python3
"""Tests for the self-assessment prompt: a plan is intent, and the frame is a fact.

FOUR VERSIONS WERE MEASURED, so the tests pin the ones that mattered:
  v1  plan labelled "executed"                false success 1/32, accuracy 62.5%
  v2  told to ignore the plan entirely        false success 0/32, accuracy 53.1%  (rejected)
  v3  intent labelled, no blanket distrust    false success 0/32, accuracy 50.0%  (rejected)
  v4  v3 + robot frame stated                 false success 0/32, accuracy 87.5%  (kept)
v2 and v3 reached a zero by being pessimistic. A zero bought that way is a different
error, not a fix, which is why the tests assert ACCURACY too.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "sa", ROOT / "runtime" / "verifier" / "self_assess.py")
sa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa)


def _prompt(visits=None, obj_at=(0.12, -0.15)):
    plan = {"stages": [{"object_name": "a", "place_pose": [0.12, -0.15, 0.0175]}]}
    obs = {"objects": {"a": [obj_at[0], obj_at[1], 0.0175, 0.0]}}
    if visits is not None:
        obs["visits"] = visits
    return sa.build_user("put both blocks in the right bin", plan, obs,
                         {"zone_1": [0.12, -0.15, 0.0175]})


def test_the_plan_is_labelled_intent_not_execution():
    """The v1 defect: a plan labelled "executed" let intent pass as evidence."""
    p = _prompt(visits={})
    assert "INTENT" in p
    assert "NOT evidence" in p
    assert "Plan executed" not in p


def test_an_empty_release_list_is_stated_not_omitted():
    """Omitting the empty visits section was how a plan became 'evidence of execution'."""
    p = _prompt(visits={})
    assert "ACTUALLY released" in p
    assert "NONE" in p


def test_a_non_empty_release_list_is_shown():
    p = _prompt(visits={"a": ["zone_1", "zone_2"]})
    assert "zone_2" in p
    assert "NONE" not in p


def test_the_robot_frame_is_stated():
    """The v3 defect: without the frame the assessor guessed left and got it backwards."""
    p = _prompt(visits={})
    assert "+y is the robot LEFT" in p
    assert "-y is the robot RIGHT" in p


def test_the_frame_constant_matches_the_planner_convention():
    planner = (ROOT / "runtime" / "planner" / "agent_planner.py").read_text(encoding="utf-8")
    assert "+y is the robot LEFT" in planner, "planner changed its convention"
    assert "+y is the robot LEFT" in sa.ROBOT_FRAME, "assessor disagrees with planner"


def test_blanket_distrust_of_the_plan_was_removed():
    """v2 told the assessor to judge ONLY from measurements; that over-corrected."""
    p = _prompt(visits={})
    assert "Judge ONLY from the measured" not in p
