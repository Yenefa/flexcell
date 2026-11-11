#!/usr/bin/env python3
"""Tests for the claim comparison and for the refusal to adopt the better-looking method.

WHY THE REFUSAL IS TESTED: the deterministic claim scored 100% and the LLM 70.3%, so the
default reading is "replace it". The reason not to is arithmetic - the plan tolerance exceeds the
slack between plan targets and the zone edge - and if that arithmetic ever stops holding, the
decision should be revisited rather than silently inherited. A test pins both.
"""
import json
import re
import sys
from pathlib import Path

# HERE is already the tests directory, so its parent is benchmark and its grandparent is
# the worktree. Using parents[2] here walked one level too far and pointed at the repo root,
# where none of these artefacts live - the same off-by-one that bit two earlier helpers.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _acc():
    return (ROOT / "setup" / "acceptance" / "evobot_claim_accuracy_20261111"
            / "accuracy.txt").read_text(encoding="utf-8")


def _blind():
    return (ROOT / "setup" / "acceptance" / "evobot_claim_accuracy_20261111"
            / "blindspot.txt").read_text(encoding="utf-8")


def test_every_llm_error_is_a_false_failure_never_a_false_success():
    """If any error were a false success the whole risk calculus changes."""
    wrong = [l for l in _acc().splitlines() if "wrong:" in l]
    assert wrong, "no errors recorded"
    for line in wrong:
        assert "passed=True" in line and "claim=False" in line, line


def test_the_deterministic_check_was_more_accurate_on_its_coverage():
    text = _acc()
    assert re.search(r"deterministic measurement check\s+coverage\s+40/64\s+correct\s+40", text)


def test_the_refusal_reason_is_arithmetic_and_still_holds():
    """plan tolerance (20 mm) must still exceed the measured slack (15 mm)."""
    slack = float(re.search(r"tightest slack\s*:\s*([\d.]+) mm", _blind()).group(1))
    plan_tol_mm = 20.0
    assert plan_tol_mm > slack, (
        "the tolerance no longer exceeds the slack - the refusal reason needs re-deriving")


def test_every_plan_target_is_measured_inside_its_zone():
    text = _blind()
    inside = int(re.search(r"inside their zone\s*:\s*(\d+)", text).group(1))
    total = int(re.search(r"stage targets examined\s*:\s*(\d+)", text).group(1))
    assert inside == total, (inside, total)


def test_the_claim_mechanism_was_not_changed():
    """This round produced evidence, not a behaviour change; the runner still uses the LLM."""
    src = (ROOT / "experiments" / "baselines" / "claim_accuracy.py").read_text(encoding="utf-8")
    assert "self_assessment.json" in src
    assert "goal_check" in src
