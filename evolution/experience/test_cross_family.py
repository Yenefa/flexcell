#!/usr/bin/env python3
"""Tests for cross-family DELIVERY: a measured win that retrieval withholds is not a win.

WHY THESE CASES
    Two modules disagreed about one entry's scope. reuse.py measured the spacing lesson
    fixing 4 instances in T12 and T03; retrieve.py gated on an EXACT task_family match and
    therefore withheld every one of them. Both modules were internally consistent and the
    measurement was arithmetically correct - it just could not reach the caller.

    The second defect underneath: task_family was a DEFAULT, not derived, so the T05 harness
    lesson declared itself a T13 spacing lesson. Because retrieval acts on that label, the
    entry was offered to the wrong tasks and invisible to the right ones at the same time.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import postmortem  # noqa: E402
import retrieve  # noqa: E402
import schema  # noqa: E402


def _active_entry(**kw):
    base = dict(origin="AGENT_GENERATED", task_family="T13_geometric_conditional",
                failure_class="control", source_run="x",
                evidence={"occurrences": 2}, applicable_when=["a"],
                known_invalid_when=[], suggested_action="widen",
                action_kind="recovery_action", consumer="executor_recovery",
                effect_spec={"fixture": "t13_two_boxes_one_bin",
                             "operator": "respread_apply",
                             "params": {"step_m": 0.09, "cluster_m": 0.12}},
                version={"label": "E", "status": "ACTIVE"},
                validation={"review_verdict": "ACCEPT", "reviewed_by": "r"})
    base.update(kw)
    return schema.make_entry(**base)


# ---------------------------------------------------------------- the gate

def test_a_measured_other_family_is_offered():
    entry = _active_entry(measured_families=["T12_triple_revisit"])
    ok, why = retrieve._gate(entry, consumer="executor_recovery",
                             task_family="T12_triple_revisit", superseded=set())
    assert ok, why


def test_the_source_family_is_still_offered():
    entry = _active_entry(measured_families=[])
    ok, why = retrieve._gate(entry, consumer="executor_recovery",
                             task_family="T13_geometric_conditional", superseded=set())
    assert ok, why


def test_an_unmeasured_family_is_withheld():
    """A measurement is not a licence: T14 was never measured and must not be offered."""
    entry = _active_entry(measured_families=["T12_triple_revisit"])
    ok, why = retrieve._gate(entry, consumer="executor_recovery",
                             task_family="T14_ordered_pair", superseded=set())
    assert not ok
    assert "not in" in why


def test_the_refusal_names_both_the_learned_and_measured_scope():
    entry = _active_entry(measured_families=["T12_triple_revisit"])
    _, why = retrieve._gate(entry, consumer="executor_recovery",
                            task_family="T14_ordered_pair", superseded=set())
    assert "T13_geometric_conditional" in why
    assert "T12_triple_revisit" in why


def test_measured_families_defaults_to_empty_not_to_everything():
    entry = _active_entry()
    assert entry["measured_families"] == []


# ---------------------------------------------------------------- the label

def test_the_harness_lesson_is_labelled_t05_not_t13():
    """It was labelled T13 by a default; its evidence is T05 batches."""
    entries, _ = postmortem.generate()
    harness = [e for e in entries if "harness" in e["version"]["label"]]
    assert harness, [e["version"]["label"] for e in entries]
    assert harness[0]["task_family"] == "T05_relay"


def test_a_family_is_derived_from_the_batch_name():
    family, why = postmortem.family_of([{"batch": "evobot_t05_batch_20261111",
                                         "path": "x"}])
    assert family == "T05_relay"
    assert "batch name" in why


def test_a_family_is_derived_from_the_runs_when_the_batch_says_nothing():
    """evobot_recover_n6_... names no template; the run's own id does."""
    family, why = postmortem.family_of([
        {"batch": "evobot_recover_n6_20261111",
         "path": "evobot_recover_n6_20261111/runs/HO-90899d657e68/task.out"}])
    assert family == "T13_geometric_conditional", why


def test_an_underivable_family_is_unknown_rather_than_a_default():
    family, why = postmortem.family_of([{"batch": "no_template_here", "path": "x"}])
    assert family == "UNKNOWN"
    assert "refusing to default" in why


def test_evidence_spanning_several_families_is_not_collapsed_to_one():
    family, why = postmortem.family_of([
        {"batch": "evobot_t05_batch_20261111", "path": "x"},
        {"batch": "evobot_t13_batch_20261111", "path": "y"}])
    assert family == "UNKNOWN"
    assert "several" in why


def test_an_entry_is_refused_when_its_family_cannot_be_derived():
    """NOT_READY, not a default: retrieval acts on the label."""
    entry, why = postmortem.build("harness_dds_exhaustion",
                                  [{"batch": "nothing", "path": "x",
                                    "detail": "", "error_code": None,
                                    "completed_stage_ids": [], "layer": "HARNESS"}] * 3)
    assert entry is None
    assert "cannot derive a task family" in why
