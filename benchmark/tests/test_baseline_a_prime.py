#!/usr/bin/env python3
"""Baseline A-prime tests: a deterministic rule planner on the real instruction texts.

No robot, no model. These test whether fixed rules can parse what the benchmark
actually asks, which is the honest measure of a FSM baseline.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "baselines"))
sys.path.insert(0, str(ROOT / "benchmark" / "generators"))

import baseline_a_prime_rules as ap
import generate as gen


def _obs(spec):
    colors = {"target_box_a": "red", "target_box_b": "blue", "target_box_c": "green"}
    return {
        "instruction": spec["instruction"],
        "objects": [{"name": o["name"], "color": colors[o["name"]],
                     "position": list(o["initial_pose"][:3])} for o in spec["objects"]],
        "zones": [{"name": z["name"], "position": z["pose"], "radius": z["radius"]}
                  for z in spec["zones"]],
    }


def test_rules_solve_t01_and_t02():
    for template in ("T01_multi_object_sorting", "T02_exclusion"):
        for seed in range(6):
            spec = gen.generate(template, seed)
            result = ap.plan(_obs(spec))
            got = {m["object"]: m["zone"] for m in result["moves"]}
            assert got == spec["expected_goal"]["placement"], (template, seed, got)


def test_rules_solve_t04_geometric_discrimination():
    for seed in range(6):
        spec = gen.generate("T04_duplicates", seed)
        result = ap.plan(_obs(spec))
        got = {m["object"]: m["zone"] for m in result["moves"]}
        assert got == spec["expected_goal"]["placement"], (seed, got)
        assert result["rule"] == "geometric"


def test_rules_cannot_solve_the_relay_template():
    # Honest limitation: the rule engine has no notion of an intermediate stop,
    # so it either mis-parses or fails. Either way it must not silently "pass".
    spec = gen.generate("T05_relay", 1000)
    try:
        result = ap.plan(_obs(spec))
    except ap.Unparsed:
        return
    got = {m["object"]: m["zone"] for m in result["moves"]}
    assert got != spec["expected_goal"]["placement"], ("rule engine should not solve relay", got)


def test_unknown_instruction_is_refused_not_guessed():
    obs = {"instruction": "Do something clever with the blocks.",
           "objects": [{"name": "target_box_a", "color": "red", "position": [0.22, 0.0, 0.0]}],
           "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0], "radius": 0.06}]}
    try:
        ap.plan(obs)
    except ap.Unparsed:
        return
    raise AssertionError("rule engine guessed instead of refusing")


def test_rule_engine_is_deterministic():
    spec = gen.generate("T01_multi_object_sorting", 1000)
    assert ap.plan(_obs(spec)) == ap.plan(_obs(spec))

