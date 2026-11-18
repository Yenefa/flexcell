#!/usr/bin/env python3
"""Tests for live-path connectivity: the loop can be correct and unplugged.

WHY THIS EXISTS
    Everything the continual-chain demo proves is proved INSIDE the chain's own harness. The
    code that hands experience to the planner for a real robot run
    (experiments/baselines/baseline_c.py) reads a DIFFERENT store with a DIFFERENT schema:

        evolution/experience/records.jsonl                          <- live path
        setup/acceptance/evobot_continual_chain_.../records_v2.jsonl <- the chain

    and zero lessons appear in both. A reader who takes "the chain works" as "the robot uses
    it" is wrong, and nothing said so until this module existed.

    The gap is not a bug to patch. Closing it means choosing which schema wins, and that
    choice changes either a fail-closed filter or the file a frozen baseline experiment reads.
    A decision with that shape has to be visible in the artifact, not made silently.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import live_path  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402


@pytest.fixture(scope="module")
def report():
    return live_path.report()


# ---------------------------------------------------------------- the live filter itself

def test_the_live_filter_requires_provenance():
    admits, why = live_path.live_filter_admits({"record_sha256": "a"}, {})
    assert admits is False
    assert "provenance" in why


def test_the_live_filter_requires_an_explicit_accept():
    """Absent ledger means NOTHING is approved - the live path's own rule."""
    admits, why = live_path.live_filter_admits(
        {"provenance_verified": True, "record_sha256": "a"}, {})
    assert admits is False
    assert "ACCEPT" in why


def test_the_live_filter_admits_a_provenance_verified_accepted_record():
    admits, why = live_path.live_filter_admits(
        {"provenance_verified": True, "record_sha256": "a"}, {"a": "ACCEPT"})
    assert admits is True and why is None


def test_a_rejected_record_is_not_admitted_even_with_provenance():
    admits, _ = live_path.live_filter_admits(
        {"provenance_verified": True, "record_sha256": "a"}, {"a": "REJECT"})
    assert admits is False


# ---------------------------------------------------------------- the real state

def test_the_report_counts_every_active_entry(report):
    assert report["active_entries"] >= 0
    assert len(report["entries"]) == report["active_entries"]


def test_the_numbers_add_up(report):
    """Every ACTIVE entry is either visible or has exactly one stated reason. A report whose
    counts do not reconcile is decoration."""
    assert sum(report["by_reason"].values()) + report["visible_to_live_path"] == \
        report["active_entries"]


def test_the_report_states_the_loop_is_unplugged(report):
    """This is the finding, pinned so it cannot be quietly dropped when the artifact is
    regenerated: the chain's ACTIVE entries are not visible to the live planning path."""
    assert report["visible_to_live_path"] < report["active_entries"]


def test_each_invisible_entry_names_why(report):
    for row in report["entries"]:
        if not row["visible"]:
            assert row.get("why"), row


def test_closing_the_gap_is_a_choice_with_a_cost(report):
    """Two options, each with a real cost. Picking one silently is the failure mode."""
    assert len(report["options"]) == 2
    for option in report["options"]:
        assert option.get("option")
        assert option.get("cost")


def test_the_claim_says_unplugged_not_broken(report):
    assert "UNPLUGGED" in report["claim"]


# ---------------------------------------------------------------- a v2 record as v1

def test_a_v2_record_put_in_the_live_store_would_still_be_filtered_out(tmp_path):
    """The concrete reason option one does not work by itself: v2 carries none of the fields
    the live filter needs."""
    entry = schema.make_entry(
        origin="AGENT_GENERATED", task_family="T05_relay", failure_class="control",
        source_run="x", evidence={"o": 1}, applicable_when=["a"], known_invalid_when=[],
        suggested_action="do the thing", action_kind="harness_config", consumer="harness",
        effect_spec={"fixture": "t05_dds_harness", "operator": "harness_capacity",
                     "params": {"participant_capacity": 120}},
        version={"label": "E", "status": "ACTIVE"},
        validation={"review_verdict": "ACCEPT", "reviewed_by": "r"})
    admits, why = live_path.live_filter_admits(entry, {})
    assert admits is False
    assert why == "no provenance_verified"
