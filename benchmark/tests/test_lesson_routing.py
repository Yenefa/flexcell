#!/usr/bin/env python3
"""Tests for lesson routing and retrieval reachability.

TWO REAL DEFECTS THESE GUARD, both found by auditing why C never differed from B:

1. DELIVERY ADDRESS. The agent plan is {moves:[{object, zone}], unmoved} and carries no
   landing coordinates, so lessons about landing spots could never change a plan from
   inside the prompt. They belong to spread_destinations.py, where they are already
   implemented.

2. UNREACHABLE LESSON. The one planner-actionable lesson mentions no task keyword, so its
   retrieval score was always 0 and it could NEVER be retrieved. The experience channel
   was empty by construction, not because experience was irrelevant.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evolution" / "experience"))
sys.path.insert(0, str(ROOT / "experiments" / "baselines"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


routing = _load("evobot_route", ROOT / "evolution" / "transfer" / "route_lessons.py")


def test_landing_lesson_routes_to_the_spread_policy_not_the_planner():
    consumer, path = routing.route(
        "Two objects sent to the same bin need distinct landing spots inside it")
    assert consumer == "spread_policy", consumer
    assert path.endswith("spread_destinations.py")


def test_domain_lesson_routes_to_the_harness():
    consumer, path = routing.route(
        "Give each run a valid distinct domain id; reusing one exhausts participants")
    assert consumer == "harness", consumer


def test_object_declaration_lesson_routes_to_the_planner():
    consumer, _ = routing.route(
        "Declare exactly the objects present in the world")
    assert consumer == "planner", consumer


def test_every_stored_lesson_is_routable():
    import store
    rows = [r for r in store.read(str(ROOT / "evolution" / "experience" / "records.jsonl"))
            if r.get("validated")]
    assert rows
    for r in rows:
        consumer, _ = routing.route(r["lesson"])
        assert consumer != "unrouted", r["lesson"]


def test_routed_lessons_are_actually_implemented_where_they_are_sent():
    """A lesson routed to a consumer that does not implement it is still lost."""
    import store
    rows = [r for r in store.read(str(ROOT / "evolution" / "experience" / "records.jsonl"))
            if r.get("validated")]
    for r in rows:
        consumer, path = routing.route(r["lesson"])
        assert routing.implemented_in(path, routing.SIGNATURES[consumer]), (
            consumer, path)

