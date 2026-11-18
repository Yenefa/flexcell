#!/usr/bin/env python3
# A standalone WORSE with no matching APPLIED run must not RETIRE an entry: one stray line
# would otherwise disable a lesson. Keep the line visible, but do not let it drive a decision.
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import ledger  # noqa: E402


def test_an_orphan_worse_is_not_counted_as_harm(tmp_path):
    p = str(tmp_path / "l.jsonl")
    ledger.append(p, "e1", "OUTCOME", run_id="orphan", outcome="WORSE", recorded_by="t")
    s = ledger.summary(p)
    assert s["e1"]["harmful"] == 0
    assert s["e1"]["applied"] == 0
    assert len(s["e1"]["unattributed_outcomes"]) == 1
    assert s["e1"]["unattributed_outcomes"][0]["outcome"] == "WORSE"


def test_a_matched_worse_still_counts_as_harm(tmp_path):
    p = str(tmp_path / "l.jsonl")
    ledger.append(p, "e1", "APPLIED", run_id="r1", recorded_by="t")
    ledger.append(p, "e1", "OUTCOME", run_id="r1", outcome="WORSE", recorded_by="t")
    s = ledger.summary(p)
    assert s["e1"]["harmful"] == 1
    assert s["e1"]["applied"] == 1
    assert s["e1"]["unattributed_outcomes"] == []


def test_an_outcome_with_no_run_is_unattributed(tmp_path):
    p = str(tmp_path / "l.jsonl")
    # OUTCOME without run_id is refused at append time by the existing rule
    import pytest
    with pytest.raises(ledger.LedgerError):
        ledger.append(p, "e1", "OUTCOME", outcome="WORSE", recorded_by="t")
