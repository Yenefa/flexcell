#!/usr/bin/env python3
"""Tests for v0.2 UNSEEN task types.

These templates exist to create headroom: v0.1 held-out is at ceiling (B 6/6), so no
improvement can be measured there. The tests ensure the new tasks are actually harder
and that their stated rules agree with their success conditions.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("benchmark/generators", "benchmark/evaluators", "experiments/baselines"):
    sys.path.insert(0, str(ROOT / p))

import unseen_tasks as U
import generate as G
import evaluate as ev
import baseline_a_prime_rules as apr


def _obs_from(spec):
    return {"instruction": spec["instruction"],
            "objects": [{"name": o["name"], "color": o["color"],
                         "position": list(o["initial_pose"][:3])} for o in spec["objects"]],
            "zones": [{"name": z["name"], "position": z["pose"], "radius": z["radius"]}
                      for z in spec["zones"]]}


def test_unseen_templates_are_not_in_the_frozen_v01_set():
    assert not (set(U.TEMPLATES) & set(G.TEMPLATES))


def test_instructions_never_leak_implementation_answers():
    banned = ["expected_goal", "evaluator", "tolerance", ".py", "skill", "visit_sequence"]
    for t in U.TEMPLATES:
        for seed in range(8):
            text = U.generate(t, seed)["instruction"].lower()
            for w in banned:
                assert w not in text, (t, seed, w)


def test_t12_requires_a_three_step_ordered_route():
    spec = U.generate("T12_triple_revisit", 7000)
    seq = spec["expected_goal"]["visit_sequence"]
    assert list(seq.values())[0] == ["zone_1", "zone_2", "zone_1"]


def test_t12_two_step_shortcut_is_rejected_by_the_ordered_clause():
    spec = U.generate("T12_triple_revisit", 7000)
    name = list(spec["expected_goal"]["placement"])[0]
    objects = {o["name"]: list(o["initial_pose"]) for o in spec["objects"]}
    objects[name] = list(U.ZONES["zone_1"]["pose"]) + [0.0]
    state = {"objects": objects, "move_sequence": [name],
            "agent_claimed_success": False,
            "visits": {name: ["zone_2", "zone_1"]}}  # skipped the first stop
    verdict = ev.evaluate(spec, state)
    assert verdict["passed"] is False
    assert "visit_sequence:" + name in verdict["failed_clauses"]


def test_t12_three_step_route_passes():
    spec = U.generate("T12_triple_revisit", 7000)
    name = list(spec["expected_goal"]["placement"])[0]
    objects = {o["name"]: list(o["initial_pose"]) for o in spec["objects"]}
    objects[name] = list(U.ZONES["zone_1"]["pose"]) + [0.0]
    state = {"objects": objects, "move_sequence": [name],
            "agent_claimed_success": False,
            "visits": {name: ["zone_1", "zone_2", "zone_1"]}}
    verdict = ev.evaluate(spec, state)
    assert verdict["passed"] is True, verdict["failed_clauses"]


def test_t13_branch_is_computed_from_measured_geometry():
    for seed in range(8):
        spec = U.generate("T13_geometric_conditional", seed)
        probe = None
        for n, o in U.OBJECTS.items():
            if o["color"] in spec["instruction"] and "block is closer" in spec["instruction"]:
                probe = n
                break
        # the correct destination is the bin OPPOSITE the nearer one
        d_left = math.hypot(U.OBJECTS["target_box_a"]["pose"][0] - U.ZONES["zone_2"]["pose"][0],
                            U.OBJECTS["target_box_a"]["pose"][1] - U.ZONES["zone_2"]["pose"][1])
        d_right = math.hypot(U.OBJECTS["target_box_a"]["pose"][0] - U.ZONES["zone_1"]["pose"][0],
                             U.OBJECTS["target_box_a"]["pose"][1] - U.ZONES["zone_1"]["pose"][1])
        assert all(z in ("zone_1", "zone_2") for z in spec["expected_goal"]["placement"].values())
        assert len(set(spec["expected_goal"]["placement"].values())) == 1


def test_t13_places_both_objects_in_the_same_bin():
    spec = U.generate("T13_geometric_conditional", 7001)
    assert len(spec["expected_goal"]["placement"]) == 2
    assert len(set(spec["expected_goal"]["placement"].values())) == 1


def test_rule_engine_cannot_solve_either_unseen_type():
    """These should be genuinely new to the deterministic baseline too."""
    for t in U.TEMPLATES:
        for seed in (7000, 7001):
            spec = U.generate(t, seed)
            try:
                result = apr.plan(_obs_from(spec))
            except apr.Unparsed:
                continue
            got = {m["object"]: m["zone"] for m in result["moves"]}
            assert got != spec["expected_goal"]["placement"], (
                t, seed, "rule engine unexpectedly solves an unseen type")


def test_unseen_specs_have_stable_sha_and_are_deterministic():
    a = U.generate("T12_triple_revisit", 7000)
    b = U.generate("T12_triple_revisit", 7000)
    assert a == b and a["instance_sha256"] == b["instance_sha256"]

