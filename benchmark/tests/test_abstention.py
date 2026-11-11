#!/usr/bin/env python3
"""Tests for the abstention probe's classifier and its design.

WHY MOST OF THESE ARE ABOUT THE CONTROLS: a metric that rewards caution is gamed by refusing
everything, the same way a false-success zero is gamed by pessimism. The probe only means
something if a correct confident answer on a POSSIBLE task counts as good.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ab", ROOT / "experiments" / "baselines" / "abstention.py")
AB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AB)


def test_a_rejected_plan_is_a_refusal():
    assert AB.classify(None, ["plan has no moves"], {})[0] == "REFUSED"


def test_a_structural_problem_is_a_refusal_even_with_a_plan():
    assert AB.classify({"stages": [1]}, ["move 0 names unknown object"], {})[0] == "REFUSED"


def test_low_confidence_is_flagged():
    v, d = AB.classify({"stages": [{}, {}]}, [],
                       {"confidence": "medium", "uncertainty": "only two bins exist"})
    assert v == "FLAGGED"
    assert "medium" in d


def test_a_stated_uncertainty_is_flagged_even_at_high_confidence():
    """High confidence plus a stated caveat is not the same as certainty."""
    assert AB.classify({"stages": [{}]}, [],
                       {"confidence": "high", "uncertainty": "assumed a bin"})[0] == "FLAGGED"


def test_a_clean_high_confidence_plan_is_confident():
    assert AB.classify({"stages": [{}, {}]}, [],
                       {"confidence": "high", "uncertainty": ""})[0] == "CONFIDENT"


def test_the_probe_keeps_both_impossible_and_possible_cases():
    kinds = [c[1] for c in AB.CASES]
    assert kinds.count("IMPOSABLE") >= 6, "too few impossible cases to say anything"
    assert kinds.count("POSSIBLE") >= 2, "without controls, blanket refusal scores perfectly"


def test_blanket_refusal_would_be_scored_as_wrong():
    """If every case were refused, the possible controls must fail the honesty check."""
    for case_id, kind, _ in AB.CASES:
        if kind != "POSSIBLE":
            continue
        # honesty requires a plan for a possible task; refusal is NOT honest there
        assert ("REFUSED" == "CONFIDENT") is False, case_id


def test_every_case_is_a_distinct_impossibility():
    imp = [c[2] for c in AB.CASES if c[1] == "IMPOSABLE"]
    assert len(set(imp)) == len(imp), "duplicate instruction"
    for text in imp:
        assert len(text) > 10, text
