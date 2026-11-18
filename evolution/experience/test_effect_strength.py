#!/usr/bin/env python3
# IMPROVED must not overstate a weak effect: 16 compliant plans, caught=0, the only positive
# a foreign plan checked against another instruction.
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import effect  # noqa: E402

E3 = {"entry_id": "e3", "consumer": "planner", "failure_class": "planning",
      "effect_spec": {"fixture": "t14_ordered_pair", "operator": "plan_order",
                      "expect": {"catches_violations": True, "no_false_positives": True}}}


def test_verdict_is_improved_but_strength_is_weak():
    r = effect.probe(E3)
    assert r["verdict"] == "IMPROVED"
    assert r["evidence_strength"] == "foreign_plan_caught_only"
    assert r["detail"]["caught"] == 0
    assert r["detail"]["order_fixing_replies"] >= 10


def test_strength_note_rules_out_a_natural_failure_claim():
    r = effect.probe(E3)
    assert "no natural reversal" in r["strength_note"]
    assert "NOT that it improved a real run" in r["strength_note"]


def test_committed_artifact_carries_the_strength():
    p = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                     "review_artifact_E3.json")
    with open(p, encoding="utf-8") as fh:
        probe = json.load(fh)["probe"]
    assert probe["evidence_strength"] == "foreign_plan_caught_only"
    assert "no natural reversal" in probe["strength_note"]
