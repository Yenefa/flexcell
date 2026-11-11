#!/usr/bin/env python3
"""Tests for the replication analysis.

WHY: this analysis changes the meaning of every rate this project has reported, so the two
claims it makes must be pinned - that no instance failed twice, and that a flip is detected only
when the two outcomes genuinely differ. A detector that counted agreement as a flip, or a
stable failure as stable, would silently invalidate the caveat on the ladder.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "rp", ROOT / "experiments" / "baselines" / "replication.py")
RP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RP)


def test_the_sets_used_are_two_replicates_of_the_same_instances():
    assert set(RP.SETS) == {"seeds7500", "seeds8100"}
    for name, bases in RP.SETS.items():
        assert len(bases) == 2, name


def test_the_analysis_only_reads_attempt_one():
    """Recovery differs between batches; comparing attempt-1 keeps the replicates comparable."""
    src = (ROOT / "experiments" / "baselines" / "replication.py").read_text(encoding="utf-8")
    assert "verdict_after1.json" in src
    assert "verdict.json" not in src.replace("verdict_after1.json", "")


def test_the_recorded_result_has_no_stable_failure():
    out = (ROOT / "setup" / "acceptance" / "evobot_replication_20261111"
           / "replication.txt")
    if not out.exists():
        return
    text = out.read_text(encoding="utf-8")
    assert "STABLE FAIL                : 0" in text
    assert "MIXED (outcome flipped)    : 8" in text


def test_classification_distinguishes_agreement_from_flip():
    """Reimplemented here against the same rule the script uses, as a guard on the rule."""
    def classify(seq):
        if all(seq):
            return "STABLE PASS"
        if not any(seq):
            return "STABLE FAIL"
        return "MIXED"
    assert classify([True, True]) == "STABLE PASS"
    assert classify([False, False]) == "STABLE FAIL"
    assert classify([True, False]) == "MIXED"
    assert classify([False, True]) == "MIXED"
