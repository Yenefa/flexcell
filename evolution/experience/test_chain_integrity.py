#!/usr/bin/env python3
"""The experience hash chain must REFUSE tampering, not just accept a clean chain.

WHY THIS EXISTS
    test_continual_chain only asserted that verify_chain ACCEPTS a clean store. A guard that
    is only ever shown passing is indistinguishable from one that always returns True. This
    whole branch rests on the chain as its trust base -- every "verified" claim leans on it --
    so the three attacks it exists to stop (edit, delete, reorder) must each be shown failing.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import store  # noqa: E402


def _chain(tmp_path, n=4):
    p = str(tmp_path / "store.jsonl")
    for i in range(n):
        row = {"entry_id": "e%d" % i, "version": {"label": "E%d" % i,
                                                 "status": "ACTIVE"},
               "suggested_action": "action %d" % i, "consumer": "executor_recovery"}
        row["record_sha256"] = store._hash(row)
        store.append(p, row)
    return p


def _rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def _write(p, rows):
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

def test_a_clean_chain_verifies(tmp_path):
    ok, msg = store.verify_chain(_chain(tmp_path))
    assert ok, msg


def test_editing_a_record_breaks_the_chain(tmp_path):
    p = _chain(tmp_path)
    rows = _rows(p)
    rows[1]["suggested_action"] = "tampered"
    _write(p, rows)
    ok, msg = store.verify_chain(p)
    assert not ok and ("mismatch" in msg or "break" in msg)


def test_deleting_a_middle_record_breaks_the_chain(tmp_path):
    p = _chain(tmp_path)
    rows = _rows(p)
    del rows[2]
    _write(p, rows)
    ok, msg = store.verify_chain(p)
    assert not ok


def test_reordering_records_breaks_the_chain(tmp_path):
    p = _chain(tmp_path)
    rows = _rows(p)
    rows[1], rows[2] = rows[2], rows[1]
    _write(p, rows)
    ok, msg = store.verify_chain(p)
    assert not ok


def test_deleting_the_tail_is_detected_by_record_count_or_not(tmp_path):
    """Honest boundary: a forward-only chain does NOT detect tail truncation by hash alone.
    Record this so the guard's limit is stated, not hidden. verify_chain must at least not
    CRASH and must still validate the remaining prefix (which is a valid shorter chain)."""
    p = _chain(tmp_path)
    rows = _rows(p)
    rows = rows[:-1]
    _write(p, rows)
    ok, _ = store.verify_chain(p)
    # The remaining prefix is internally consistent -- this asserts the known LIMIT, not a
    # pass. Deleting the tail needs an external anchor (e.g. a published head), which this
    # store does not have; that limit is documented rather than papered over.
    assert ok is True
