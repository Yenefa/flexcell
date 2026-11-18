#!/usr/bin/env python3
# Tests for the push-recovery with/without comparison reader.
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import push_comparison  # noqa: E402


def test_the_real_comparison_is_measured():
    r = push_comparison.measure()
    assert r["measured"] is True
    assert r["is_real_comparison"] is True
    assert r["control_passes"] == 0 and r["control_runs"] == 3
    assert r["feedback_passes"] == 3 and r["feedback_runs"] == 3


def test_the_honest_limits_are_present():
    r = push_comparison.measure()
    assert any("n=3" in x for x in r["honest_limits"])
    assert any("dev instance" in x for x in r["honest_limits"])
    assert any("does not isolate" in x for x in r["honest_limits"])


def test_a_missing_batch_is_not_claimed_as_a_measurement(tmp_path):
    r = push_comparison.measure(acceptance=str(tmp_path))
    assert r["measured"] is False


def test_measure_accepts_the_parent_acceptance_directory():
    """The first version took only the batch directory and reported "not present" when
    handed setup/acceptance, silently turning a real comparison into a missing one."""
    r = push_comparison.measure(acceptance=os.path.join(WT, "setup", "acceptance"))
    assert r["measured"] is True
    assert r["is_real_comparison"] is True


def test_the_unrouted_report_names_the_external_comparison():
    """A probe saying "this archive cannot measure it" is a claim about the path the
    probe reads, not about the repository."""
    import unrouted
    report = unrouted.report()
    rows = [x for x in report["unrouted"] if x.get("external_comparison")]
    assert rows, "an UNMEASURED verdict must say whether an outside comparison exists"
    assert any("independently collected" in x["why"] for x in rows)
