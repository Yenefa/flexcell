#!/usr/bin/env python3
"""Tests for routing coverage: a declared destination is not a covered one.

WHY THIS EXISTS
    consumers.implemented() checks that a consumer's entrypoint FILE exists. That says the
    address is real; it does not say any mail ever arrived. The objective names four
    routings and this stack declares all four - so a check written against the declaration
    reports 4/4 while one of them has never carried an entry.

    The gap is not hypothetical: offering a ROS-launch lesson to "development" returns
    UNSUPPORTED, i.e. the routing exists and nothing can arrive. That is the same
    routed-but-undeliverable defect this package fixed twice for other consumers.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import delivery  # noqa: E402
import routing_coverage  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402

RECORDS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                       "records_v2.jsonl")


def _entry(consumer, action_kind, label="E"):
    return schema.make_entry(
        origin="AGENT_GENERATED", task_family="T05_relay", failure_class="control",
        source_run="x", evidence={"o": 1}, applicable_when=["a"], known_invalid_when=[],
        suggested_action="do the thing", action_kind=action_kind, consumer=consumer,
        effect_spec={"fixture": "t05_dds_harness", "operator": "harness_capacity",
                     "params": {"participant_capacity": 120}},
        version={"label": label, "status": "ACTIVE"},
        validation={"review_verdict": "ACCEPT", "reviewed_by": "r"})


# ---------------------------------------------------------------- the coverage report

def test_all_four_objective_routings_are_reported():
    report = routing_coverage.coverage(RECORDS)
    assert report["named"] == 4
    assert {r["consumer"] for r in report["routings"]} == {
        "planner", "spread_policy", "executor_recovery", "development"}


def test_a_declared_consumer_with_no_entry_is_reported():
    """The whole point: 'declared' must not be allowed to look like 'covered'.

    The state is now NO_ENTRY (the path works, nothing is routed here) rather than the old
    blanket NAMED_BUT_EMPTY, because that blanket hid a delivered path from a missing one.
    """
    report = routing_coverage.coverage(RECORDS)
    by = {r["consumer"]: r for r in report["routings"]}
    assert by["development"]["state"] in (routing_coverage.NO_ENTRY,
                                          routing_coverage.NAMED_BUT_EMPTY)
    assert by["development"]["state"] != routing_coverage.CARRIED
    assert by["development"]["active_entries"] == []


def test_the_report_does_not_round_the_gap_up():
    report = routing_coverage.coverage(RECORDS)
    assert report["carried"] < report["named"]


def test_a_routing_carries_only_when_an_ACTIVE_entry_reaches_its_consumer():
    report = routing_coverage.coverage(RECORDS)
    for row in report["routings"]:
        if row["state"] == routing_coverage.CARRIED:
            assert row["active_entries"], row
        else:
            assert row["why"], row


def test_a_candidate_entry_does_not_count_as_coverage(tmp_path):
    """A CANDIDATE is not live; counting it would report a destination as covered by
    something that cannot be retrieved."""
    entry = _entry("development", "development")
    entry["version"] = dict(entry["version"], status="CANDIDATE")
    path = tmp_path / "s.jsonl"
    store.append(str(path), entry)
    report = routing_coverage.coverage(str(path))
    by = {r["consumer"]: r for r in report["routings"]}
    assert by["development"]["state"] != routing_coverage.CARRIED


def test_an_entry_with_no_trigger_does_not_become_coverage(tmp_path):
    """The delivery path exists now, but a development entry with no applicable_when is
    DROPPED, so it still must not be counted as carried."""
    entry = _entry("development", "development")
    entry["applicable_when"] = []
    path = tmp_path / "s.jsonl"
    store.append(str(path), entry)
    report = routing_coverage.coverage(str(path))
    by = {r["consumer"]: r for r in report["routings"]}
    assert by["development"]["state"] != routing_coverage.CARRIED
    assert by["development"]["active_entries"] == ["E"]


def test_acting_from_an_unnamed_consumer_is_reported_separately():
    """The ROS-launch lesson DOES act - from "harness", which the objective did not name.
    Counting that as coverage of the fourth routing would be the rounding-up this module
    exists to prevent."""
    report = routing_coverage.coverage(RECORDS)
    assert "harness" in report["carried_by_an_unnamed_consumer"]
    assert "harness" not in {r["consumer"] for r in report["routings"]}


def test_every_routing_row_states_a_reason():
    report = routing_coverage.coverage(RECORDS)
    for row in report["routings"]:
        assert row["why"].strip(), row


def test_an_unbacked_live_rule_is_reported():
    """A rule wired straight into the code path acts with no entry behind it. That is
    WORSE than an empty routing, not better: it cannot be reviewed, probed for misuse,
    recorded, revised or retired, because there is no entry to hang any of that on."""
    report = routing_coverage.coverage(RECORDS)
    assert "live_rules_with_no_entry" in report
    # the planner's order rule is gated on an admitted entry, so this must be empty
    assert report["live_rules_with_no_entry"] == []


def test_the_claim_says_an_unbacked_rule_is_worse_than_an_empty_routing():
    report = routing_coverage.coverage(RECORDS)
    assert "worse than an empty routing" in report["claim"]


def test_the_claim_says_what_is_not_counted():
    report = routing_coverage.coverage(RECORDS)
    assert "separately" in report["claim"]


# ---------------------------------------------------------------- the underlying gap

def test_development_had_no_delivery_path_and_now_has_one():
    """The gap was real and is now closed - pinned in both directions so neither the fix nor
    the original defect can be forgotten."""
    assert "development" in consumers.CONSUMERS
    assert consumers.implemented("development") is True, \
        "its entrypoint file exists, which is why 'implemented' was never the right check"
    out = delivery.deliver({"entry_id": "x", "consumer": "development",
                            "suggested_action": "check the DDS participant pool",
                            "applicable_when": ["launching many nodes"]}, None)
    assert out["verdict"] == delivery.DELIVERED
    # ... but a DEVELOPMENT entry with no trigger is still refused
    dropped = delivery.deliver({"entry_id": "x", "consumer": "development",
                                "suggested_action": "check the DDS participant pool"}, None)
    assert dropped["verdict"] == delivery.DROPPED
