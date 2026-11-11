#!/usr/bin/env python3
"""Tests for the order-constraint template and its three-way execution classification.

WHY THREE STATES: the first analyser used a boolean and I read False as "executed out of
order". The evidence was observed=["target_box_a"], matched=1, out_of_order=[] - the second
move was never recorded because the run stopped. Calling that "out of order" invents a failure
mode that never happened, and the two mean opposite things about the agent: stopping early is an
execution problem, reordering is a comprehension problem.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "generators"))
import unseen_tasks as U                            # noqa: E402

spec = importlib.util.spec_from_file_location(
    "op", ROOT / "experiments" / "baselines" / "ordered_pair.py")
OP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OP)


def test_the_template_exists_and_carries_an_order_constraint():
    assert "T14_ordered_pair" in U.TEMPLATES
    s = U.generate("T14_ordered_pair", 9300, "held_out")
    order = s["expected_goal"]["order"]
    assert len(order) == 2 and order[0] != order[1]
    assert s["constraints"]["order"] == order
    # the instruction must state the requirement, not just imply it
    assert "FIRST" in s["instruction"]
    assert "not acceptable" in s["instruction"]


def test_the_template_is_not_a_copy_of_an_existing_one():
    s14 = U.generate("T14_ordered_pair", 9300, "held_out")
    s13 = U.generate("T13_geometric_conditional", 9300, "held_out")
    assert "order" not in (s13["expected_goal"] or {})
    assert "order" in (s14["expected_goal"] or {})


def test_the_template_is_deterministic_for_a_seed():
    a = U.generate("T14_ordered_pair", 9301, "held_out")
    b = U.generate("T14_ordered_pair", 9301, "held_out")
    assert a["instance_sha256"] == b["instance_sha256"]


def test_complete_sequence_is_in_order():
    assert OP.classify(["a", "b"], ["a", "b"]) == "in-order"


def test_a_correct_prefix_is_incomplete_not_wrong_order():
    assert OP.classify(["a"], ["a", "b"]) == "INCOMPLETE"


def test_a_reversed_sequence_is_wrong_order():
    assert OP.classify(["b", "a"], ["a", "b"]) == "WRONG-ORDER"


def test_an_empty_sequence_is_incomplete():
    assert OP.classify([], ["a", "b"]) == "INCOMPLETE"


def test_no_requirement_means_no_conclusion():
    assert OP.classify(["a", "b"], []) == "no-requirement"


def test_the_real_batch_contains_no_reordering():
    base = Path("/tmp/evobot-batch4")
    if not base.is_dir() or not Path("/etc/evobot/sealed").is_dir():
        return
    for d in sorted(base.glob("HO-*")):
        try:
            ans = json.loads((Path("/etc/evobot/sealed") / (d.name + ".json")).read_text(
                encoding="utf-8"))
        except Exception:
            return
        req = (ans.get("expected_goal") or {}).get("order") or []
        obs_p = d / "observation_after1.json"
        if not obs_p.exists():
            continue
        seq = json.loads(obs_p.read_text(encoding="utf-8")).get("move_sequence") or []
        assert OP.classify(seq, req) != "WRONG-ORDER", d.name
