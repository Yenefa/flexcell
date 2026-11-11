#!/usr/bin/env python3
"""Tests that the cross-type control is a real control, and that luck is not counted as skill.

WHY: the headline correction rests on two claims that are easy to fake - that the pre-T14 rule
set really lacks the T14 rule, and that the 5 instances it "got right" were luck rather than
understanding. If either is untrue the correction is worthless.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "rc", ROOT / "experiments" / "baselines" / "rule_crosstype.py")
RC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RC)

OBS = {"objects": [{"name": "a", "color": "red", "position": [0.22, 0.0, 0.0175]},
                   {"name": "b", "color": "blue", "position": [0.2, -0.18, 0.0175]}],
       "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0175], "radius": 0.06},
                 {"name": "zone_2", "position": [0.25, 0.05, 0.0175], "radius": 0.06}],
       "skills": ["observe", "pick", "place"]}


def test_a_natural_order_success_is_not_evidence_of_parsing():
    """Required [a,b] equals the enumeration order, so a rule set that ignores order scores."""
    obs = OBS
    moves = [{"object": "a", "zone": "zone_2"}, {"object": "b", "zone": "zone_2"}]
    goal = {"order": ["a", "b"], "placement": {"a": "zone_2", "b": "zone_2"}}
    assert RC._parses_order(obs, moves, goal) is False


def test_a_non_natural_order_success_is_evidence_of_parsing():
    obs = OBS
    moves = [{"object": "b", "zone": "zone_2"}, {"object": "a", "zone": "zone_2"}]
    goal = {"order": ["b", "a"], "placement": {"a": "zone_2", "b": "zone_2"}}
    assert RC._parses_order(obs, moves, goal) is True


def test_ignoring_a_non_natural_order_is_not_parsing():
    obs = OBS
    moves = [{"object": "a", "zone": "zone_2"}, {"object": "b", "zone": "zone_2"}]
    goal = {"order": ["b", "a"], "placement": {"a": "zone_2", "b": "zone_2"}}
    assert RC._parses_order(obs, moves, goal) is False


def test_the_pre_t14_copy_lacks_the_t14_rule_but_keeps_the_others():
    pre = (ROOT / "runtime" / "planner" / "rule_planner_pre_t14.py").read_text(
        encoding="utf-8")
    full = (ROOT / "runtime" / "planner" / "rule_planner.py").read_text(encoding="utf-8")
    assert "must be put there FIRST" in full
    assert "must be put there FIRST" not in pre
    # the relay and conditional rules must still be present, or the comparison is unfair
    assert "then move it to the" in pre
    assert "closer to the" in pre
    assert "def plan(" in pre
