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


# ---------------------------------------------------------------- the ledger

def test_the_audit_can_record_each_task_it_used_the_skill_on(tmp_path):
    """Step 5 asks WHICH TASK. The audit used to write that to a report and nowhere else,
    so the ledger showed two applications under one demo label while seven real tasks had
    been handled."""
    import ledger as ledger_mod
    path = str(tmp_path / "l.jsonl")
    assets = skill_asset.read(ASSETS)
    entry_id = "e" * 64
    report = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                         source_task=SOURCE, ledger_path=path, entry_id=entry_id,
                         record=True)
    summary = ledger_mod.summary(path)
    rec = summary[entry_id]
    # APPLIED counts every plan the skill was offered to, not only the ones it changed:
    # the wins are a SUBSET. Asserting equality here was the wins-only bias written into a
    # test, where it would have locked the defect in.
    assert rec["applied"] > report["total_instances_fixed"] > 0
    assert rec["helpful"] == report["total_instances_fixed"]
    assert rec["harmful"] == 0


def test_every_recorded_task_gets_its_own_three_rows(tmp_path):
    """'offered but inert' and 'applied and helped' must not look alike."""
    import ledger as ledger_mod
    path = str(tmp_path / "l.jsonl")
    assets = skill_asset.read(ASSETS)
    reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                source_task=SOURCE, ledger_path=path, entry_id="e" * 64, record=True)
    by_run = {}
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        by_run.setdefault(row["run_id"], set()).add(row["event"])
    assert by_run
    for run, events in by_run.items():
        # A task id is either a sealed instance ("HO-...") or a dev-split run
        # ("T01-train-seed1000"). Asserting only "HO-" excluded every dev-split task.
        assert run.startswith("HO-") or "-seed" in run, run
        assert {"RETRIEVED", "APPLIED", "OUTCOME"} <= events, run


def test_an_inert_application_is_recorded_too(tmp_path):
    """THE MIRROR OF THE ERROR THE LEDGER WARNS ABOUT.

    Its docstring records "one lesson was retrieved for every task and changed no plan".
    Recording only the winners inverts the bias: every application looks like it changed
    the outcome. Measured on this archive, that is a 100% hit rate reported for a 2.4%
    effect.
    """
    import ledger as ledger_mod
    path = str(tmp_path / "l.jsonl")
    assets = skill_asset.read(ASSETS)
    report = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                         source_task=SOURCE, ledger_path=path, entry_id="e" * 64,
                         record=True)
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    outcomes = [r for r in rows if r["event"] == "OUTCOME"]
    kinds = {r.get("outcome") for r in outcomes}
    assert "IMPROVED" in kinds
    assert "UNCHANGED" in kinds, "the inert applications were dropped from the ledger"
    # the denominator must be the whole archive, not just the wins
    assert len(outcomes) > 10 * report["total_instances_fixed"]


def test_the_recorded_hit_rate_is_not_flattered(tmp_path):
    path = str(tmp_path / "l.jsonl")
    assets = skill_asset.read(ASSETS)
    reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                source_task=SOURCE, ledger_path=path, entry_id="e" * 64, record=True)
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    applied = [r for r in rows if r["event"] == "APPLIED"]
    changed = [r for r in applied if r.get("changed")]
    assert len(applied) > 100
    assert len(changed) < len(applied) / 2, "a ledger that only says 100% is not measuring"


def test_every_outcome_row_has_a_matching_applied_row(tmp_path):
    """An outcome without an application would be a result with no cause."""
    path = str(tmp_path / "l.jsonl")
    assets = skill_asset.read(ASSETS)
    reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                source_task=SOURCE, ledger_path=path, entry_id="e" * 64, record=True)
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    applied = {(r["run_id"], r["event"]) for r in rows if r["event"] == "APPLIED"}
    for row in rows:
        if row["event"] == "OUTCOME":
            assert (row["run_id"], "APPLIED") in applied, row["run_id"]


def test_the_report_never_divides_across_units():
    """fixed is per task instance; untouched was once per plan file.

    The same task appears in several batches, so the plan-file denominator is about 3x the
    instance denominator. A rate built from one of each understated the effect by that
    factor - a real headline said 2.4% where the honest figure was 6.4%.
    """
    assets = skill_asset.read(ASSETS)
    report = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                         source_task=SOURCE)
    assert report["instances_offered"] > 0
    assert report["plans_offered"] > report["instances_offered"], \
        "if these were equal the batch duplication would be untested"
    fixed = report["total_instances_fixed"]
    assert abs(report["instance_hit_rate"] - fixed / float(report["instances_offered"])) < 1e-3


def test_the_instance_hit_rate_differs_from_the_plan_rate():
    """Guard against the two being silently interchangeable."""
    assets = skill_asset.read(ASSETS)
    report = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                         source_task=SOURCE)
    offered_plans = report["plans_offered"]
    fixed = report["total_instances_fixed"]
    plan_rate = fixed / float(offered_plans)
    assert abs(plan_rate - report["instance_hit_rate"]) > 0.01, \
        "a same-unit denominator would make this test vacuous"


def test_untouched_is_counted_per_instance_and_per_plan():
    assets = skill_asset.read(ASSETS)
    report = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                         source_task=SOURCE)
    plans = sum(r["untouched_plans"] for r in report["families"].values())
    instances = sum(r["untouched_instances"] for r in report["families"].values())
    assert plans > instances > 0


def test_the_instance_and_plan_offered_counts_agree_on_totals():
    """Each offered plan is exactly one of fixed/untouched/worse/refused, and each offered
    instance likewise - so both totals must be internally consistent."""
    assets = skill_asset.read(ASSETS)
    report = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                         source_task=SOURCE)
    per_plans = sum(r["newly_fixed_instances"] + r["untouched_plans"] + r["made_worse"]
                    + r["refused"] for r in report["families"].values())
    assert report["plans_offered"] == per_plans


def test_recording_off_writes_nothing(tmp_path):
    """The measurement must stay usable as a pure report."""
    path = tmp_path / "l.jsonl"
    assets = skill_asset.read(ASSETS)
    reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                source_task=SOURCE, ledger_path=str(path), entry_id="e" * 64,
                record=False)
    assert not path.exists()


def test_the_audit_result_is_unchanged_by_recording(tmp_path):
    """Turn on the ledger and the numbers must be identical: recording is not part of the
    measurement."""
    assets = skill_asset.read(ASSETS)
    plain = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                        source_task=SOURCE)
    recorded = reuse.audit(assets[0], acceptance=os.path.join(WT, "setup", "acceptance"),
                           source_task=SOURCE, ledger_path=str(tmp_path / "l.jsonl"),
                           entry_id="e" * 64, record=True)
    for key in ("total_instances_fixed", "total_made_worse", "families_with_fixes"):
        assert plain[key] == recorded[key], key


def test_an_empty_archive_reports_no_claims(tmp_path):
    report = reuse.audit(_asset(), acceptance=str(tmp_path), source_task="X")
    assert report["total_instances_fixed"] == 0
    assert report["families_fixed_beyond_the_source"] == []
