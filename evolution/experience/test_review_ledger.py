#!/usr/bin/env python3
"""Tests for the tamper-evident review ledger.

WHY THIS EXISTS
    live_binding gates a live robot parameter on an independent ACCEPT. The ledger carrying
    that ACCEPT was a plain JSONL file, so anyone could append a line with a made-up reviewer
    name and the gate would authorise apply_respread. The chain makes insertion/editing after
    the fact detectable. It does NOT prove reviewer identity (needs a signature) and does not
    stop a reviewer appending a NEW review; both limits are stated in the module docstring.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import live_binding  # noqa: E402
import review_ledger  # noqa: E402


def test_an_empty_ledger_does_not_verify(tmp_path):
    assert review_ledger.verify(str(tmp_path / "none"))[0] is False


def test_one_review_verifies(tmp_path):
    path = tmp_path / "ledger.jsonl"
    review_ledger.append(str(path), {"entry_id": "e", "verdict": "ACCEPT",
                                     "reviewed_by": "auditor"})
    ok, why = review_ledger.verify(str(path))
    assert ok, why
    assert "1" in why


def test_many_reviews_verify_in_order(tmp_path):
    path = tmp_path / "ledger.jsonl"
    for i in range(5):
        review_ledger.append(str(path), {"entry_id": "e%d" % i, "verdict": "ACCEPT",
                                         "reviewed_by": "auditor"})
    ok, why = review_ledger.verify(str(path))
    assert ok, why
    assert "5" in why


def test_editing_a_review_breaks_the_chain(tmp_path):
    path = tmp_path / "ledger.jsonl"
    review_ledger.append(str(path), {"entry_id": "e", "verdict": "ACCEPT",
                                     "reviewed_by": "auditor"})
    row = json.loads(open(path, encoding="utf-8").readline())
    row["verdict"] = "REJECT"
    path.write_text(json.dumps(row) + chr(10), encoding="utf-8")
    ok, why = review_ledger.verify(str(path))
    assert not ok
    assert "hash" in why or "mismatch" in why


def test_deleting_a_middle_review_breaks_the_chain(tmp_path):
    path = tmp_path / "ledger.jsonl"
    for i in range(3):
        review_ledger.append(str(path), {"entry_id": "e%d" % i, "verdict": "ACCEPT",
                                         "reviewed_by": "auditor"})
    lines = open(path, encoding="utf-8").readlines()
    # delete the MIDDLE record. A forward-only hash chain cannot detect truncation of its
    # tail (the remaining prefix is a valid shorter chain), so the honest claim is about
    # deletion/reordering/editing of records that other records point past, not about tail
    # truncation. A test that deleted the tail and expected failure would assert something
    # a hash chain does not provide.
    path.write_text(lines[0] + lines[2], encoding="utf-8")
    ok, why = review_ledger.verify(str(path))
    assert not ok
    assert "break" in why


def test_an_inserted_line_is_detected(tmp_path):
    path = tmp_path / "ledger.jsonl"
    review_ledger.append(str(path), {"entry_id": "real", "verdict": "ACCEPT",
                                     "reviewed_by": "auditor"})
    lines = open(path, encoding="utf-8").readlines()
    forged = {"entry_id": "real", "verdict": "ACCEPT", "reviewed_by": "made-up"}
    lines.insert(0, json.dumps(forged) + chr(10))
    path.write_text("".join(lines), encoding="utf-8")
    assert review_ledger.verify(str(path))[0] is False


def test_a_forged_ledger_cannot_authorise_a_live_call(tmp_path):
    """The whole point: the gate must not hand parameters to a robot from an editable file."""
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps({"entry_id": "anything", "verdict": "ACCEPT",
                                "reviewed_by": "whoever"}) + chr(10), encoding="utf-8")
    kwargs, why = live_binding.resolve(
        os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                     "skill_assets.jsonl"),
        "executor_recovery",
        os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                     "records_v2.jsonl"),
        review_ledger=str(path))
    assert kwargs == {}
    assert "intact" in why or "chain" in why
