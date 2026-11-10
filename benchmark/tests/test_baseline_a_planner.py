#!/usr/bin/env python3
"""Baseline A planner tests: mechanical, deterministic, spec-derived."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "baselines"))
sys.path.insert(0, str(ROOT / "benchmark" / "generators"))

import baseline_a_composite as ba
import generate as gen


def test_every_implemented_template_produces_a_stage_list():
    for template in gen.TEMPLATES:
        spec = gen.generate(template, 1000)
        stages = ba.plan_from_spec(spec)
        assert stages, template
        assert len(stages) <= 8, (template, "RunComposite allows at most 8 stages")
        for s in stages:
            assert s["stage_id"] and s["object_name"] and len(s["place_pose"]) == 3


def test_protected_objects_never_appear_as_stages():
    for template in gen.TEMPLATES:
        for seed in (1000, 2000, 9000):
            spec = gen.generate(template, seed)
            protected = set(spec["expected_goal"].get("unmoved") or [])
            moved = {s["object_name"] for s in ba.plan_from_spec(spec)}
            assert not (protected & moved), (template, seed, protected & moved)


def test_ordered_template_preserves_the_stated_order():
    spec = gen.generate("T03_ordered", 1001)
    order = spec["expected_goal"]["order"]
    stages = ba.plan_from_spec(spec)
    assert [s["object_name"] for s in stages] == order


def test_relay_template_inserts_an_intermediate_place():
    spec = gen.generate("T05_relay", 1000)
    stages = ba.plan_from_spec(spec)
    assert len(stages) == 2, stages
    assert stages[0]["place_pose"] != stages[1]["place_pose"]


def test_planning_is_deterministic():
    spec = gen.generate("T01_multi_object_sorting", 1000)
    assert ba.plan_from_spec(spec) == ba.plan_from_spec(spec)


def test_planner_does_not_mutate_the_spec():
    spec = gen.generate("T02_exclusion", 1000)
    before = json.dumps(spec, sort_keys=True)
    ba.plan_from_spec(spec)
    assert json.dumps(spec, sort_keys=True) == before

