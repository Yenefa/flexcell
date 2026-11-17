#!/usr/bin/env python3
"""Tests for the reuse audit: does a stored skill help tasks it was NOT built from?

WHY THESE CASES
    "It works on the input it was derived from" is the weakest possible claim and it is the
    one a demo naturally produces. A reuse audit that only counted fixes would also reward
    an asset for thrashing conforming plans. And a report that conflates cross-FAMILY
    reuse with cross-SPLIT transfer says "it generalizes" without anything having been
    shown. Each test below pins one of those.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))

import reuse  # noqa: E402
import skill_asset  # noqa: E402

ASSETS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                      "skill_assets.jsonl")
SOURCE = "HO-90899d657e68"


def _resp_plan(sep, x=0.12):
    stages = [{"stage_id": "s0", "object_name": "a",
               "place_pose": [x - sep / 2.0, -0.15, 0.0175]},
              {"stage_id": "s1", "object_name": "b",
               "place_pose": [x + sep / 2.0, -0.15, 0.0175]}]
    return {"task_id": "SYNTH", "stages": stages,
            "initial_objects": [{"object_name": "b0", "position": [0.22, 0.0, 0.0]},
                                {"object_name": "b1", "position": [0.20, -0.18, 0.0]}]}


def _asset():
    assets = skill_asset.read(ASSETS)
    return next(a for a in assets if a["callable"]["function"] == "apply_respread")


# ---------------------------------------------------------------- the audit

def test_the_audit_reports_per_family_not_just_a_total():
    report = reuse.audit(_asset(), source_task=SOURCE)
    families = report["families"]
    assert families
    for row in families.values():
        for key in ("newly_fixed_instances", "untouched_plans", "made_worse",
                    "refused"):
            assert key in row


def test_the_audit_finds_fixes_outside_the_source_family():
    """The claim under test: a lesson from one family helps ANOTHER family."""
    report = reuse.audit(_asset(), source_task=SOURCE)
    assert report["source_family"] == "T13_geometric_conditional"
    beyond = report["families_fixed_beyond_the_source"]
    assert beyond, report["families"]
    assert "T13_geometric_conditional" not in beyond


def test_the_audit_counts_each_task_instance_once():
    """The same instance appears in several batches; counting files would inflate it."""
    report = reuse.audit(_asset(), source_task=SOURCE)
    for row in report["families"].values():
        assert len(row["instances"]) == row["newly_fixed_instances"], row


def test_the_audit_reports_zero_harm():
    report = reuse.audit(_asset(), source_task=SOURCE)
    assert report["total_made_worse"] == 0


def test_the_audit_reports_untouched_conforming_plans():
    """An asset that touches a conforming plan is a defect, not a bonus."""
    report = reuse.audit(_asset(), source_task=SOURCE)
    assert sum(r["untouched_plans"] for r in report["families"].values()) > 0


def test_the_report_states_the_claim_it_does_NOT_support():
    """Cross-family is not cross-split, and the report must say so itself."""
    report = reuse.audit(_asset(), source_task=SOURCE)
    assert "NOT cross-split" in report["claim"]


def test_an_unknown_template_is_not_guessed_from_the_id():
    """An unresolvable id must report UNKNOWN, not be filed under a convenient family."""
    assert reuse.template_of("NOT-A-REAL-TASK-ID") == "UNKNOWN"


def test_a_refusing_asset_is_recorded_not_crashed(tmp_path):
    """A consumer that raises is data about the archive, not an exception to swallow."""
    bad = {"asset_id": "skill.test.bad",
           "callable": {"module": "runtime.recovery.recover",
                        "function": "apply_respread", "kwargs": {}},
           "guard": ["x"]}
    report = reuse.audit(bad, acceptance=str(tmp_path), source_task="X")
    assert report["total_instances_fixed"] == 0


def test_an_empty_archive_reports_no_claims(tmp_path):
    report = reuse.audit(_asset(), acceptance=str(tmp_path), source_task="X")
    assert report["total_instances_fixed"] == 0
    assert report["families_fixed_beyond_the_source"] == []
