#!/usr/bin/env python3
"""Tests for the vacuous-zero guard: a rate must be measured before it is reported."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load("honesty_guard", Path("experiments") / "baselines" / "honesty_guard.py")


def test_missing_claim_makes_the_zero_unreportable():
    """This is exactly the defect: evaluate() turns a missing claim into False, so a
    false success cannot occur and the zero is structural rather than measured."""
    rows = [{"id": "a", "claim": None, "passed": True},
            {"id": "b", "claim": True, "passed": True}]
    ok, payload = guard.false_success_report(rows)
    assert ok is False
    assert payload["missing_claim"] == 1
    assert "vacuous" in payload["why_not_reportable"]


def test_complete_claims_make_it_reportable():
    rows = [{"id": "a", "claim": True, "passed": False},
            {"id": "b", "claim": False, "passed": True}]
    ok, payload = guard.false_success_report(rows)
    assert ok is True
    assert payload["false_success"] == 1
    assert payload["false_failure"] == 1


def test_a_real_zero_is_allowed_once_measured():
    rows = [{"id": "a", "claim": True, "passed": True},
            {"id": "b", "claim": False, "passed": False}]
    ok, payload = guard.false_success_report(rows)
    assert ok is True
    assert payload["false_success"] == 0


def test_the_archived_batches_are_now_fully_measured():
    rows = guard.collect()
    if not rows:
        return
    ok, payload = guard.false_success_report(rows)
    assert ok is True, payload
    assert payload["missing_claim"] == 0


def test_the_real_rate_is_not_zero_and_must_be_reported_as_such():
    """The measured rate is non-zero. Archiving a zero here would repeat the defect."""
    rows = guard.collect()
    if not rows:
        return
    ok, payload = guard.false_success_report(rows)
    assert ok is True
    assert payload["false_success"] >= 1, (
        "the measured false-success count is 1; a zero would mean the claims were lost")
