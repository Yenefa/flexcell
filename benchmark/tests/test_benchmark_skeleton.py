#!/usr/bin/env python3
"""Offline tests for the EvoBot benchmark skeleton.

These run with no ROS, no Gazebo and no network: the TaskSpec contract, the
generator and the independent evaluator are the parts that must be trustworthy
before any robot moves, because everything else is judged through them.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "evaluators"))
sys.path.insert(0, str(ROOT / "benchmark" / "generators"))

import evaluate as ev
import generate as gen

SCHEMA = json.loads((ROOT / "benchmark/schemas/taskspec.schema.json").read_text(encoding="utf-8"))


def _state(objects, claimed=False, sequence=None):
    return {"objects": objects, "agent_claimed_success": claimed,
            "move_sequence": sequence or []}


def _at(zone_name):
    z = gen.ZONES[zone_name]["pose"]
    return [z[0], z[1], 0.0175, 0.0]


def _full_state(spec, overrides=None, claimed=False, sequence=None):
    """A complete observation: EVERY declared object, moved only where overridden.

    A real observation always covers the whole scene, so a fixture that omits an
    object is not a valid "everything is fine" state - the evaluator is right to
    fail it, because "I did not see it" is not "it did not move".
    """
    objects = {o["name"]: list(o["initial_pose"]) for o in spec["objects"]}
    objects.update(overrides or {})
    return _state(objects, claimed=claimed, sequence=sequence)


def test_declared_objects_match_the_world_the_robot_actually_builds():
    # Regression for a real failure: every RunComposite plan was rejected with
    # "plan must declare every observed object", because the generator declared a
    # third box that the default world does not contain. The scene composition is a
    # property of the world, so the generator must draw from it.
    scene = gen.SCENES[gen.DEFAULT_SCENE]
    assert scene["objects"] == ["target_box_a", "target_box_b"]
    for template in gen.TEMPLATES:
        spec = gen.generate(template, 1000)
        declared = [o["name"] for o in spec["objects"]]
        assert declared == sorted(scene["objects"]), (template, declared)


def test_no_template_depends_on_an_object_the_default_world_lacks():
    allowed = set(gen.SCENES[gen.DEFAULT_SCENE]["objects"])
    for template in gen.TEMPLATES:
        for seed in range(8):
            spec = gen.generate(template, seed)
            used = {o["name"] for o in spec["objects"]}
            used |= set(spec["expected_goal"].get("placement") or {})
            used |= set(spec["expected_goal"].get("unmoved") or [])
            assert used <= allowed, (template, seed, used - allowed)


def test_t04_instruction_and_expected_goal_agree():
    """Regression: the instruction once said the OPPOSITE of expected_goal.

    An agent that read the instruction correctly would have been graded FAIL. A task
    whose stated rule contradicts its own success condition is not a hard task, it is
    an impossible one.
    """
    import math
    spec = gen.generate("T04_duplicates", 1000)
    poses = {o["name"]: o["initial_pose"] for o in spec["objects"]}
    dist = {n: math.hypot(p[0], p[1]) for n, p in poses.items()}
    placement = spec["expected_goal"]["placement"]
    to_right = [n for n, z in placement.items() if z == "zone_1"][0]
    to_left = [n for n, z in placement.items() if z == "zone_2"][0]
    # the instruction sends the FURTHER block to the right bin
    assert dist[to_right] > dist[to_left], (dist, placement)
    # and it must warn that colour is misleading
    assert "colour" in spec["instruction"].lower()


def test_t04_no_longer_claims_the_blocks_look_alike():
    # They are red and blue; claiming otherwise made the instruction false.
    spec = gen.generate("T04_duplicates", 1000)
    assert "look alike" not in spec["instruction"].lower()


def test_evaluator_and_generator_versions_agree():
    assert ev.EVALUATOR_VERSION == gen.EVALUATOR_VERSION


def test_each_implemented_template_generates_a_valid_spec():
    required = SCHEMA["required"]
    for template in gen.TEMPLATES:
        spec = gen.generate(template, 1)
        for key in required:
            assert key in spec, (template, key)
        assert spec["template_id"] == template
        assert spec["evaluator_version"] == ev.EVALUATOR_VERSION
        assert spec["execution_budget"]["max_steps"] >= 1


def test_unimplemented_templates_refuse_instead_of_inventing_expectations():
    for template, why in gen.NOT_IMPLEMENTED.items():
        assert why, template
        with pytest.raises(NotImplementedError):
            gen.generate(template, 1)


def test_generation_is_deterministic_and_hashed():
    a = gen.generate("T03_ordered", 42)
    b = gen.generate("T03_ordered", 42)
    assert a == b
    assert a["instance_sha256"] == b["instance_sha256"]
    assert len(a["instance_sha256"]) == 64
    c = gen.generate("T03_ordered", 43)
    assert c["instance_sha256"] != a["instance_sha256"]


def test_instructions_do_not_leak_implementation_answers():
    # A task statement must describe the goal, never the solution.
    banned = ["skill", "move_to_pose", "pick_server", "place_server", ".py", ".cpp",
              "yaml", "function", "patch", "diff", "line ", "grasp(", "import "]
    for template in gen.TEMPLATES:
        for seed in range(6):
            text = gen.generate(template, seed)["instruction"].lower()
            for word in banned:
                assert word not in text, (template, seed, word, text)


def test_t01_passes_only_when_both_objects_are_in_their_bins():
    spec = gen.generate("T01_multi_object_sorting", 3)
    placement = spec["expected_goal"]["placement"]
    names = list(placement)
    good = {n: _at(placement[n]) for n in names}
    verdict = ev.evaluate(spec, _full_state(spec, good, claimed=True))
    assert verdict["passed"] is True, verdict["failed_clauses"]
    assert verdict["false_success"] is False

    swapped = {n: _at(placement[names[1 - i]]) for i, n in enumerate(names)}
    verdict = ev.evaluate(spec, _full_state(spec, swapped, claimed=True))
    assert verdict["passed"] is False
    assert verdict["false_success"] is True, "claiming a wrong result must be caught"


def test_a_held_object_is_not_a_placed_object():
    spec = gen.generate("T01_multi_object_sorting", 3)
    placement = spec["expected_goal"]["placement"]
    names = list(placement)
    hovering = {n: _at(placement[n]) for n in names}
    hovering[names[0]] = [hovering[names[0]][0], hovering[names[0]][1], 0.12, 0.0]
    verdict = ev.evaluate(spec, _full_state(spec, hovering))
    assert verdict["passed"] is False
    assert any("placement:" in c for c in verdict["failed_clauses"])


def test_t02_fails_if_the_protected_object_moved():
    spec = gen.generate("T02_exclusion", 5)
    keep = spec["expected_goal"]["unmoved"][0]
    placed = {n: _at(zone) for n, zone in spec["expected_goal"]["placement"].items()}
    verdict = ev.evaluate(spec, _full_state(spec, placed))
    assert verdict["passed"] is True, verdict["failed_clauses"]

    moved = dict(placed)
    moved[keep] = _at("zone_1")
    verdict = ev.evaluate(spec, _full_state(spec, moved))
    assert verdict["passed"] is False
    assert "unmoved:" + keep in verdict["failed_clauses"]


def test_t03_detects_wrong_order_even_when_all_bins_are_correct():
    spec = gen.generate("T03_ordered", 7)
    order = spec["expected_goal"]["order"]
    objects = {n: _at("zone_1") for n in order}
    verdict = ev.evaluate(spec, _full_state(spec, objects, sequence=list(order)))
    assert verdict["passed"] is True, verdict["failed_clauses"]

    reversed_seq = list(reversed(order))
    verdict = ev.evaluate(spec, _full_state(spec, objects, sequence=reversed_seq))
    assert verdict["passed"] is False
    assert "order" in verdict["failed_clauses"]


def test_claiming_success_does_not_change_the_measurement():
    spec = gen.generate("T01_multi_object_sorting", 3)
    quiet = ev.evaluate(spec, _full_state(spec, claimed=False))
    loud = ev.evaluate(spec, _full_state(spec, claimed=True))
    assert quiet["passed"] == loud["passed"] is False
    assert quiet["false_success"] is False
    assert loud["false_success"] is True


def test_evaluator_is_pure_and_does_not_mutate_inputs():
    spec = gen.generate("T01_multi_object_sorting", 3)
    before = json.dumps(spec, sort_keys=True)
    objects = {n: _at("zone_1") for n in spec["expected_goal"]["placement"]}
    state = _state(objects)
    snapshot = json.dumps(state, sort_keys=True)
    first = ev.evaluate(spec, state)
    second = ev.evaluate(spec, state)
    assert first == second
    assert json.dumps(spec, sort_keys=True) == before
    assert json.dumps(state, sort_keys=True) == snapshot


def test_missing_object_is_a_failure_not_a_crash():
    spec = gen.generate("T02_exclusion", 5)
    verdict = ev.evaluate(spec, _state({}))
    assert verdict["passed"] is False
    assert verdict["failed_clauses"]

