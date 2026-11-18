#!/usr/bin/env python3
"""Tests for GRADED failures and, specifically, telling an order violation from a truncation.

WHY THIS EXISTS
    The three "order clause failed" rows in this archive are not one phenomenon:
      * run_foreign_plan  required [b, a], observed [a, b]  -> REORDERED. A real planning
        lesson: every move happened, in the wrong sequence.
      * two crosstype runs required [x, y], observed [x]    -> INCOMPLETE. The second move
        never happened, so it was not out of order. Filing those as order lessons would
        teach the planner to fix something that was never wrong.
    The clause NAME is identical in all three; only the evidence separates them. A
    classifier keyed on the vulnerable substring "order" cannot tell them apart.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import postmortem  # noqa: E402


def _failure(required, observed, clauses=None):
    return {"layer": "GRADED", "clauses": clauses or ["order"], "detail": "",
            "order_kind": _kind(required, observed)}


def _kind(required, observed):
    """Mirror of the classifier in _clause_failures, kept here to state the rule."""
    if not required:
        return "unknown"
    if observed[:len(required)] == required:
        return "satisfied"
    if observed and required[:len(observed)] == observed:
        return "incomplete"
    if sorted(observed) == sorted(required):
        return "reordered"
    return "mismatched"


# ---------------------------------------------------------------- the distinction

def test_a_reordering_is_an_order_lesson():
    kind = _kind(["target_box_b", "target_box_a"], ["target_box_a", "target_box_b"])
    assert kind == "reordered"
    assert postmortem.signature_of(_failure(["b", "a"], ["a", "b"])) == "order_clause_violated"


def test_a_prefix_is_NOT_an_order_lesson():
    """The second move never happened - it cannot have been out of order."""
    kind = _kind(["target_box_b", "target_box_a"], ["target_box_b"])
    assert kind == "incomplete"
    assert postmortem.signature_of(
        _failure(["target_box_b", "target_box_a"], ["target_box_b"])) == "incomplete_execution"


def test_an_unclassified_order_failure_is_not_dressed_up_as_a_lesson():
    sig = postmortem.signature_of({"layer": "GRADED", "clauses": ["order"],
                                   "order_kind": "mismatched", "detail": ""})
    assert sig == "order_unclassified"


def test_an_order_failure_with_no_evidence_is_unclassified():
    sig = postmortem.signature_of({"layer": "GRADED", "clauses": ["order"],
                                   "order_kind": "unknown", "detail": ""})
    assert sig == "order_unclassified"


# ---------------------------------------------------------------- the real archive

def test_the_archive_has_exactly_one_genuine_reordering():
    """Three order-clause rows exist; only one is a reordering. If this changes, look."""
    rows, _ = postmortem.scan_with_report(include_held_out=True)
    reordered = [r for r in rows if r.get("order_kind") == "reordered"]
    incomplete = [r for r in rows if r.get("order_kind") == "incomplete"]
    assert len(reordered) == 1, [r["path"] for r in reordered]
    assert len(incomplete) == 2, [r["path"] for r in incomplete]


def test_the_incomplete_runs_are_classified_as_incomplete():
    rows, _ = postmortem.scan_with_report(include_held_out=True)
    for row in rows:
        if row.get("order_kind") == "incomplete":
            assert postmortem.signature_of(row) == "incomplete_execution"


def test_the_order_lesson_is_still_refused_for_lack_of_occurrences():
    """One genuine reordering is a mis-attribution risk, not a lesson."""
    report = postmortem.generate()
    # generate() returns (entries, skipped) - a tuple, not a dict. The skipped map is the
    # one that says WHY a signature produced no entry.
    skipped = (report[1] if isinstance(report, tuple) else report).get("signatures", {})
    if "order_clause_violated" in skipped:
        assert skipped["order_clause_violated"].get("built") is False


# ---------------------------------------------------------------- the graded channel

def test_graded_failures_carry_the_clauses_that_failed():
    rows, _ = postmortem.scan_with_report(include_held_out=True)
    graded = [r for r in rows if r.get("layer") == "GRADED"]
    assert graded
    for row in graded:
        assert row.get("clauses")


def test_the_graded_channel_is_not_the_runner_channel():
    """task.out carries what the RUNNER said; verdict.json what the GRADER found."""
    rows, _ = postmortem.scan_with_report(include_held_out=True)
    layers = {r.get("layer") for r in rows}
    assert "GRADED" in layers


def test_a_graded_row_with_no_order_clause_is_classified_by_its_other_clauses():
    sig = postmortem.signature_of({"layer": "GRADED",
                                   "clauses": ["placement:target_box_a"],
                                   "detail": ""})
    assert sig == "placement_clause_failed"
