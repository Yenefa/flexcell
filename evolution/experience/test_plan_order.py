#!/usr/bin/env python3
"""Tests for the plan-side order check, and for measuring the planner without a model.

WHY THIS EXISTS
    The planner's SYSTEM PROMPT says "If the instruction fixes an order, follow it exactly."
    Until this check existed that sentence was advice nobody verified: validate_plan looked
    only at whether object and bin names were known. The archive holds ONE plan that reversed
    a required order, and it was found only AFTER a full robot run - which is the expensive
    way to find out something knowable before the arm moves.

    The subtlety these tests pin: every plan the agent wrote for its OWN task obeyed the
    order. The single archived reversal is a plan authored for one task and executed against
    ANOTHER, so it only shows up when the check is given the HOST instruction. A probe that
    scans same-run pairs alone reports zero violations and the check looks untested.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import agent_planner  # noqa: E402
import effect  # noqa: E402

ORDER_OBS = {
    "instruction": ("Put both blocks in the left bin. The blue block must be put there "
                    "FIRST, then the red block. Doing it in the other order is not "
                    "acceptable even if both end up in the right bin."),
    "objects": [{"name": "target_box_a", "color": "red"},
                {"name": "target_box_b", "color": "blue"}],
    "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0]}],
}
NO_ORDER_OBS = {
    "instruction": "Put both blocks in the right bin.",
    "objects": [{"name": "target_box_a", "color": "red"},
                {"name": "target_box_b", "color": "blue"}],
    "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0]}],
}
GREEN_THEN_RED = [{"object": "target_box_b", "zone": "zone_1"},
                  {"object": "target_box_a", "zone": "zone_1"}]
RED_THEN_GREEN = [{"object": "target_box_a", "zone": "zone_1"},
                  {"object": "target_box_b", "zone": "zone_1"}]


# ---------------------------------------------------------------- the check

def test_a_reversed_order_is_refused():
    problem = agent_planner.check_plan_order(ORDER_OBS, RED_THEN_GREEN)
    assert problem
    assert "target_box_b" in problem and "FIRST" in problem


def test_the_required_order_is_accepted():
    assert agent_planner.check_plan_order(ORDER_OBS, GREEN_THEN_RED) is None


def test_an_instruction_with_no_order_clause_is_inert():
    """The check must not invent a requirement the instruction never stated."""
    assert agent_planner.check_plan_order(NO_ORDER_OBS, RED_THEN_GREEN) is None
    assert agent_planner.check_plan_order(NO_ORDER_OBS, GREEN_THEN_RED) is None


def test_a_plan_that_ignores_the_object_entirely_is_a_different_fault():
    """Not moving it at all is not 'out of order', and a check that conflates them
    reports a fault it did not find."""
    assert agent_planner.check_plan_order(
        ORDER_OBS, [{"object": "target_box_a", "zone": "zone_1"}]) is None


def test_validate_plan_carries_the_order_problem_ONLY_when_an_entry_is_admitted():
    """The rule must not be live on its own.

    Wiring it straight into validate_plan made the planner refuse plans it used to accept -
    a live behaviour change with no entry behind it, so nothing could review it, probe it
    for misuse, record an outcome for it, or retire it. Step 4 of the objective is explicit
    that a change is validated and versioned BEFORE it is enabled.
    """
    _, without = agent_planner.validate_plan({"moves": RED_THEN_GREEN}, ORDER_OBS)
    assert not any("FIRST" in p for p in without), \
        "the rule fired with no admitted entry - an unreviewed live behaviour change"

    admitted = dict(ORDER_OBS)
    admitted["experience"] = [{"failure_class": "planning",
                               "lesson": "emit moves in the stated order",
                               "_entry_id": "e" * 64}]
    _, with_entry = agent_planner.validate_plan({"moves": RED_THEN_GREEN}, admitted)
    assert any("FIRST" in p for p in with_entry)
    _, clean = agent_planner.validate_plan({"moves": GREEN_THEN_RED}, admitted)
    assert clean == []


def test_the_order_rule_is_still_measurable_without_being_live():
    """Measuring the rule is not the same as enabling it."""
    assert agent_planner.check_plan_order(ORDER_OBS, RED_THEN_GREEN)
    assert agent_planner.order_rule_admitted(ORDER_OBS) is False


def test_an_entry_marker_without_an_id_does_not_admit_the_rule():
    """Delivery stamps _entry_id. A bare lesson string must not be enough, or any text
    reaching the observation would enable a rule nobody reviewed."""
    obs = dict(ORDER_OBS)
    obs["experience"] = [{"failure_class": "planning", "lesson": "do the thing"}]
    assert agent_planner.order_rule_admitted(obs) is False


def test_the_check_is_still_not_a_correctness_judgement():
    """It refuses an order reversal, not a wrong bin: the evaluator owns correctness."""
    wrong_bin = [{"object": "target_box_b", "zone": "zone_1"},
                 {"object": "target_box_a", "zone": "zone_1"}]
    _, problems = agent_planner.validate_plan({"moves": wrong_bin}, ORDER_OBS)
    assert problems == []


# ---------------------------------------------------------------- the measurement

def test_the_planner_now_has_a_model_free_effect_operator():
    out = effect.probe({"entry_id": "x", "consumer": "planner",
                        "failure_class": "planning",
                        "effect_spec": {"fixture": "t14_ordered_pair",
                                        "operator": "plan_order",
                                        "expect": {"catches_violations": True,
                                                   "no_false_positives": True}}})
    assert out["verdict"] == "IMPROVED", out
    assert out["expectations_met"] is True


def test_the_probe_catches_the_archived_foreign_reordering():
    """The archive's one genuine reversal is a plan run against ANOTHER task's instruction."""
    out = effect.probe({"entry_id": "x", "consumer": "planner",
                        "failure_class": "planning",
                        "effect_spec": {"fixture": "t14_ordered_pair",
                                        "operator": "plan_order"}})
    assert out["detail"]["archived_foreign_reordering_caught"] is True


def test_the_probe_wrongly_refuses_nothing():
    out = effect.probe({"entry_id": "x", "consumer": "planner",
                        "failure_class": "planning",
                        "effect_spec": {"fixture": "t14_ordered_pair",
                                        "operator": "plan_order"}})
    assert out["detail"]["false_positives"] == 0
    assert out["detail"]["compliant_passed_through"] == 16


def test_the_operator_does_not_claim_the_plan_IMPROVED_end_to_end():
    """It measures the validator, not the model's plan. Same-run violations are zero."""
    out = effect.probe({"entry_id": "x", "consumer": "planner",
                        "failure_class": "planning",
                        "effect_spec": {"fixture": "t14_ordered_pair",
                                        "operator": "plan_order"}})
    assert out["detail"]["violations"] == 0


def test_the_order_lesson_is_still_refused_for_lack_of_occurrences():
    """A working check does not make ONE reordering enough evidence for a lesson."""
    import postmortem
    report = postmortem.generate()[1]["signatures"]
    if "order_clause_violated" in report:
        assert report["order_clause_violated"]["built"] is False


PASS_THROUGH_OBS = {'instruction': ('Move the blue block to the left bin, passing '
                                  'through the right bin first.'),
                    'objects': [{'name': 'b', 'color': 'blue'}],
                    'zones': [{'name': 'zone_1', 'position': [0.12, -0.15, 0.0175]},
                              {'name': 'zone_2', 'position': [0.25, 0.05, 0.0175]}]}
WRONG_ROUTE = [{'object': 'b', 'zone': 'zone_1'},
               {'object': 'b', 'zone': 'zone_2'}]
RIGHT_ROUTE = [{'object': 'b', 'zone': 'zone_2'},
               {'object': 'b', 'zone': 'zone_1'}]


def test_a_reversed_pass_through_route_is_caught():
    problem = agent_planner.check_plan_order(PASS_THROUGH_OBS, WRONG_ROUTE)
    assert problem and 'right bin first' in problem


def test_a_correct_pass_through_route_is_not_flagged():
    assert agent_planner.check_plan_order(PASS_THROUGH_OBS, RIGHT_ROUTE) is None


def test_an_unknown_bin_word_is_not_guessed():
    obs = dict(PASS_THROUGH_OBS)
    obs['instruction'] = 'passing through the middle bin first'
    assert agent_planner._required_first_zone(obs) is None


def test_the_bin_is_resolved_from_the_observation_not_from_the_answer():
    zone, why = agent_planner._required_first_zone(PASS_THROUGH_OBS)
    assert zone == 'zone_2'
    assert 'right bin' in why


def test_the_pass_through_rule_is_still_gated_by_an_admitted_entry():
    assert agent_planner.order_rule_admitted(PASS_THROUGH_OBS) is False
