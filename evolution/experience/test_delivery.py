#!/usr/bin/env python3
"""Tests for delivery: routing says which module CAN act; this says the entry ARRIVED.

WHY THESE CASES
    The defect this guards is silent. The planner's prompt renderer reads item["lesson"]
    while a v2 entry carries suggested_action, so the lesson vanished, the plan did not
    change, and the ledger recorded NO_CHANGE - indistinguishable from "the lesson had no
    effect". Nothing raised. Every test below fails if that silence comes back.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))

import delivery  # noqa: E402
import public_observation as po  # noqa: E402
import schema  # noqa: E402

TASK = os.path.join(WT, "benchmark", "held_out", "unseen_public", "HO-90899d657e68.json")


@pytest.fixture(scope="module")
def observation():
    return po.build_observation(json.loads(open(TASK, encoding="utf-8").read()))


def planner_entry(**kw):
    base = dict(origin="AGENT_GENERATED", task_family="T14-ordered-pair",
                failure_class="planning", source_run="x",
                evidence={"order_clause_failures": 3},
                applicable_when=["the instruction fixes which block goes first"],
                known_invalid_when=[],
                suggested_action="emit the moves in the order the instruction states",
                action_kind="move_order", consumer="planner",
                effect_spec={"fixture": "t14_ordered_pair", "operator": "delivery"},
                version={"label": "E-order", "status": "CANDIDATE"})
    base.update(kw)
    return schema.make_entry(**base)


# ---------------------------------------------------------------- the field mismatch

def test_the_entry_carries_suggested_action_not_lesson():
    """This IS the mismatch. If the schema ever gains a lesson field, revisit delivery."""
    entry = planner_entry()
    assert entry.get("suggested_action")
    assert "lesson" not in entry


def test_actionable_text_prefers_suggested_action_and_says_so():
    text, source = delivery.actionable_text(planner_entry())
    assert text and source == "suggested_action"


def test_actionable_text_accepts_a_v1_lesson_record():
    """Old store records use lesson; refusing them would strand archived experience."""
    text, source = delivery.actionable_text({"lesson": "do the thing", "consumer": "planner"})
    assert text == "do the thing" and source == "lesson"


def test_an_entry_with_no_text_is_dropped():
    out = delivery.deliver({"entry_id": "x", "consumer": "planner"}, None)
    assert out["verdict"] == "DROPPED"


# ---------------------------------------------------------------- the planner path

def test_the_rendered_lesson_actually_reaches_the_prompt(observation):
    out = delivery.deliver(planner_entry(), observation)
    assert out["verdict"] == "DELIVERED"
    assert out["delivered"] is True


def test_the_raw_entry_does_NOT_reach_the_prompt(observation):
    """The negative control: without a renderer the text is invisible to describe()."""
    import agent_planner
    raw = po.build_observation(json.loads(open(TASK, encoding="utf-8").read()))
    raw["experience"] = [planner_entry()]
    assert "emit the moves in the order" not in agent_planner.describe(raw)


def test_the_renderer_puts_the_text_where_describe_reads_it(observation):
    import agent_planner
    enriched = delivery.deliver_planner(planner_entry(), observation)
    rendered = agent_planner.describe(enriched)
    assert "emit the moves in the order" in rendered
    assert enriched["experience"][-1]["lesson"].startswith("emit the moves")


def test_planner_delivery_without_an_observation_is_unsupported():
    out = delivery.deliver(planner_entry(), None)
    assert out["verdict"] == "UNSUPPORTED"


# ---------------------------------------------------------------- the other paths

def test_a_parameter_consumer_delivers_by_binding_a_callable():
    entry = planner_entry(consumer="executor_recovery", action_kind="recovery_action",
                          suggested_action="widen spacing",
                          effect_spec={"fixture": "t13_two_boxes_one_bin",
                                       "operator": "respread_apply",
                                       "params": {"step_m": 0.09, "cluster_m": 0.12}})
    out = delivery.deliver(entry, None)
    assert out["verdict"] == "DELIVERED"
    assert out["callable"]["function"] == "apply_respread"


def test_a_prompt_only_entry_is_never_silently_treated_as_delivered():
    out = delivery.deliver({"entry_id": "x", "consumer": "planner",
                            "suggested_action": "do it"}, None)
    assert out["verdict"] != "DELIVERED"


def test_a_consumer_with_no_delivery_path_is_unsupported():
    out = delivery.deliver({"entry_id": "x", "consumer": "development",
                            "suggested_action": "record the practice"}, None)
    assert out["verdict"] == "UNSUPPORTED"


def test_the_three_verdicts_are_distinct():
    """DELIVERED / DROPPED / UNSUPPORTED must not collapse into one another."""
    assert len({delivery.DELIVERED, delivery.DROPPED, delivery.UNSUPPORTED}) == 3
