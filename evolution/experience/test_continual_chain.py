#!/usr/bin/env python3
"""Tests for the continual chain: entry -> consumer -> behaviour -> verification.

WHY THESE CASES
    Every test here corresponds to a failure that actually happened in this repository,
    or to the specific way a naive implementation passes while doing nothing:
      * a lesson delivered to a consumer that cannot express it (byte-identical plans);
      * a record retrievable before anyone reviewed it (two false lessons reached a plan);
      * a store whose activation rewrote history (the hash chain would then reject it);
      * curation counting a reviewed successor as a duplicate (weight doubled);
      * an "effect" that is narrated rather than executed.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import curate  # noqa: E402
import effect  # noqa: E402
import ledger  # noqa: E402
import retrieve  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402

BASE = dict(
    origin="AGENT_GENERATED",
    task_family="T13-conditional-two-boxes",
    failure_class="control",
    source_run="setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68",
    evidence={"clearance_m": 0.05, "place_error_m": 0.00965},
    applicable_when=["two stages land in the same bin"],
    known_invalid_when=["a single stage lands in the bin"],
    suggested_action="separate same-bin landing points by clearance plus measured drift",
    effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                 "params": {"step_m": 0.090}},
)


def entry(**kw):
    args = dict(BASE)
    args.update(kw)
    return schema.make_entry(**args)


# ---------------------------------------------------------------- schema

def test_valid_entry_has_no_problems():
    assert schema.validate(entry(action_kind="landing_spacing",
                                 consumer="spread_policy",
                                 version={"label": "E1", "status": "CANDIDATE"})) == []


def test_entry_edited_after_write_is_detected():
    e = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"})
    e["suggested_action"] = "something else entirely"
    assert any("entry_id does not match" in p for p in schema.validate(e))


def test_agent_generated_entry_cannot_self_accept():
    e = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "ACTIVE"},
              validation={"review_verdict": "ACCEPT", "reviewed_by": None})
    assert any("without a reviewer" in p for p in schema.validate(e))


def test_effect_spec_without_fixture_is_refused():
    with pytest.raises(schema.EntryError):
        entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"},
              effect_spec={"operator": "spread_step"})


def test_master_goal_seven_fields_are_all_carried():
    e = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"},
              validation={"review_verdict": "ACCEPT", "reviewed_by": "r",
                          "review_ref": "REVIEW.md"})
    coverage = schema.master_goal_coverage(e)
    assert set(coverage) == {"1_source_experiment", "2_raw_evidence",
                             "3_applicable_task", "4_applicable_conditions",
                             "5_known_invalid_conditions", "6_confidence_state",
                             "7_verification_record"}
    assert all(coverage.values()), coverage


# ---------------------------------------------------------------- routing

def test_capability_routing_picks_the_consumer_that_declares_the_kind():
    consumer, why = consumers.route({"action_kind": "landing_spacing",
                                     "consumer": "spread_policy"})
    assert consumer == "spread_policy" and "capability" in why


def test_routing_refuses_a_consumer_that_cannot_express_the_kind():
    """The original defect: a landing-spot lesson offered to a planner with no pose field."""
    with pytest.raises(consumers.RoutingError):
        consumers.route({"action_kind": "landing_spacing", "consumer": "planner"})


def test_unknown_kind_is_unrouted_not_forced():
    consumer, why = consumers.route({"action_kind": "harness_config"})
    assert consumer in ("harness", None)


# ---------------------------------------------------------------- effect

def test_planner_side_spread_reports_no_change_on_an_already_spread_plan():
    e = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"})
    probe = effect.probe(e)
    assert probe["verdict"] == "NO_CHANGE", probe
    assert probe["changed"] is False


def test_executor_side_respread_actually_changes_the_plan():
    e = entry(action_kind="recovery_action", consumer="executor_recovery",
              version={"label": "E2", "status": "CANDIDATE"},
              effect_spec={"fixture": "t13_two_boxes_one_bin",
                           "operator": "respread_apply",
                           "params": {"step_m": 0.090, "cluster_m": 0.12}})
    probe = effect.probe(e)
    assert probe["verdict"] == "CHANGED", probe
    assert probe["applied_min_separation_m"] >= 0.09 - 1e-9
    # the T13 failure was a landing point 46 mm from box_b; the fix must keep clearance
    assert probe["applied_min_clearance_m"] >= 0.05, probe


def test_prompt_level_consumer_is_unmeasured_not_no_effect():
    """A planner lesson cannot be scored offline; calling that NO_CHANGE would be a lie."""
    e = entry(action_kind="move_order", consumer="planner",
              version={"label": "E3", "status": "CANDIDATE"},
              effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "none"})
    probe = effect.probe(e)
    assert probe["verdict"] == "UNMEASURED"
    assert "model call" in probe["why"]


def test_expectation_is_checked_against_measured_numbers():
    e = entry(action_kind="recovery_action", consumer="executor_recovery",
              version={"label": "E2", "status": "CANDIDATE"},
              effect_spec={"fixture": "t13_two_boxes_one_bin",
                           "operator": "respread_apply",
                           "params": {"step_m": 0.090},
                           "expect": {"applied_min_separation_m_gte": 0.20}})
    probe = effect.probe(e)
    assert probe["changed"] is True
    assert probe["expectations_met"] is False


# ---------------------------------------------------------------- curation

def test_duplicate_is_refused_instead_of_double_counted():
    a = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"})
    decision, _related, _why = curate.classify([a], a)
    assert decision == "DUPLICATE"


def test_same_condition_different_operator_is_a_conflict():
    a = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"})
    b = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"},
              effect_spec={"fixture": "t13_two_boxes_one_bin",
                           "operator": "recovery_action",
                           "params": {"failure_class": "planning", "action": "respread"}})
    decision, _related, _why = curate.classify([a], b)
    assert decision == "CONFLICT"


def test_same_operator_different_parameters_supersedes_and_merges_evidence():
    a = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "ACTIVE"},
              effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                           "params": {"step_m": 0.090}})
    b = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E2", "status": "CANDIDATE"},
              evidence={"clearance_m": 0.05, "place_error_m": 0.0119,
                        "second_run_seconds": 28.6},
              effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                           "params": {"step_m": 0.100}})
    decision, _related, _why = curate.classify([a], b)
    assert decision == "SUPERSEDE"
    ev, runs, files = curate.merge_evidence([a, b])
    # detail is KEPT across both observations rather than one overwriting the other
    assert ev["place_error_m"] in (0.00965, 0.0119)
    assert ev["second_run_seconds"] == 28.6


def test_conflicting_evidence_values_are_named_not_silently_picked():
    a = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "ACTIVE"})
    b = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E2", "status": "CANDIDATE"},
              evidence={"clearance_m": 0.05, "place_error_m": 0.031})
    ev, _runs, _files = curate.merge_evidence([a, b])
    assert "_conflicts" in ev and "place_error_m" in ev["_conflicts"]


def test_a_reviewed_successor_is_a_chain_not_a_duplicate(tmp_path):
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    cand = entry(action_kind="landing_spacing", consumer="spread_policy",
                 version={"label": "E1", "status": "CANDIDATE"})
    store.append(str(store_path), cand)
    curate.activate(cand["entry_id"],
                    {"review_verdict": "ACCEPT", "reviewed_by": "reviewer",
                     "review_ref": "REVIEW.md"},
                    store_path=str(store_path), ledger_path=str(ledger_path))
    report = curate.curate(store.read(str(store_path)))
    assert report["duplicates"] == []
    assert len(report["chains"]) == 1
    assert report["chains"][0]["statuses"] == ["CANDIDATE", "ACTIVE"]


# ---------------------------------------------------------------- activation

def test_activation_appends_a_successor_and_keeps_the_candidate(tmp_path):
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    cand = entry(action_kind="landing_spacing", consumer="spread_policy",
                 version={"label": "E1", "status": "CANDIDATE"})
    store.append(str(store_path), cand)
    successor = curate.activate(cand["entry_id"],
                                {"review_verdict": "ACCEPT", "reviewed_by": "r"},
                                store_path=str(store_path), ledger_path=str(ledger_path))
    rows = store.read(str(store_path))
    assert len(rows) == 2
    assert rows[0]["entry_id"] == cand["entry_id"]  # candidate retained, unchanged
    assert rows[1]["entry_id"] == successor["entry_id"]
    assert successor["version"]["parent_entry_id"] == cand["entry_id"]
    ok, msg = store.verify_chain(str(store_path))
    assert ok, msg


def test_activation_without_a_reviewer_is_refused(tmp_path):
    store_path = tmp_path / "s.jsonl"
    cand = entry(action_kind="landing_spacing", consumer="spread_policy",
                 version={"label": "E1", "status": "CANDIDATE"})
    store.append(str(store_path), cand)
    with pytest.raises(schema.EntryError):
        curate.activate(cand["entry_id"], {"review_verdict": "ACCEPT"},
                        store_path=str(store_path),
                        ledger_path=str(tmp_path / "l.jsonl"))


# ---------------------------------------------------------------- retrieval

def _activate(tmp_path, name="s", **kw):
    # Distinct file names per call: two calls in one test would otherwise hit the
    # store's duplicate-record guard and look like a defect in the guard.
    store_path = tmp_path / (name + ".jsonl")
    ledger_path = tmp_path / (name + "_ledger.jsonl")
    cand = entry(**kw)
    store.append(str(store_path), cand)
    succ = curate.activate(cand["entry_id"],
                           {"review_verdict": "ACCEPT", "reviewed_by": "reviewer"},
                           store_path=str(store_path), ledger_path=str(ledger_path))
    return store_path, ledger_path, succ


def test_retrieval_refuses_a_candidate_and_admits_an_activated_entry(tmp_path):
    e = entry(action_kind="landing_spacing", consumer="spread_policy",
              version={"label": "E1", "status": "CANDIDATE"})
    store_path = tmp_path / "s.jsonl"
    store.append(str(store_path), e)
    kept, report = retrieve.retrieve("spread_policy", store_path=str(store_path),
                                     ledger_path=str(tmp_path / "l.jsonl"),
                                     record=False)
    assert kept == []
    assert report["refused"][0]["why"].startswith("status is")

    store_path2, ledger_path2, _succ = _activate(
        tmp_path, name="s2", action_kind="landing_spacing", consumer="spread_policy",
        version={"label": "E1", "status": "CANDIDATE"})
    kept2, _r2 = retrieve.retrieve("spread_policy", store_path=str(store_path2),
                                   ledger_path=str(ledger_path2), record=False)
    assert len(kept2) == 1


def test_retrieval_refuses_an_entry_the_consumer_cannot_act_on(tmp_path):
    store_path, ledger_path, _succ = _activate(
        tmp_path, action_kind="landing_spacing", consumer="spread_policy",
        version={"label": "E1", "status": "CANDIDATE"})
    kept, report = retrieve.retrieve("executor_recovery", store_path=str(store_path),
                                     ledger_path=str(ledger_path), record=False)
    assert kept == []
    assert any("does not declare" in r["why"] for r in report["refused"])


def test_retrieval_refuses_a_whole_broken_chain(tmp_path):
    store_path, ledger_path, _succ = _activate(
        tmp_path, action_kind="landing_spacing", consumer="spread_policy",
        version={"label": "E1", "status": "CANDIDATE"})
    rows = [json.loads(line) for line in store_path.read_text().splitlines() if line]
    # Delete the FIRST record and keep the successor: its prev_sha256 now points at a
    # record that no longer exists, which is the deletion the chain must detect.
    store_path.write_text(json.dumps(rows[1]) + "\n", encoding="utf-8")
    with pytest.raises(retrieve.RetrievalRefused):
        retrieve.retrieve("spread_policy", store_path=str(store_path),
                          ledger_path=str(ledger_path), record=False)


def test_an_empty_retrieval_is_recorded(tmp_path):
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    store_path.write_text("", encoding="utf-8")
    kept, _report = retrieve.retrieve("spread_policy", store_path=str(store_path),
                                      ledger_path=str(ledger_path), record=True)
    assert kept == []
    rows = ledger.read(str(ledger_path))
    assert rows and rows[-1]["entry_id"] == "NO_ENTRY"


# ---------------------------------------------------------------- ledger

def test_applied_and_outcome_require_a_run_id(tmp_path):
    path = str(tmp_path / "l.jsonl")
    with pytest.raises(ledger.LedgerError):
        ledger.append(path, "e1", "APPLIED")
    with pytest.raises(ledger.LedgerError):
        ledger.append(path, "e1", "OUTCOME")


def test_effect_state_reports_harm_before_help(tmp_path):
    path = str(tmp_path / "l.jsonl")
    ledger.append(path, "e1", "APPLIED", run_id="r1")
    ledger.append(path, "e1", "OUTCOME", run_id="r1", outcome="IMPROVED")
    ledger.append(path, "e1", "APPLIED", run_id="r2")
    ledger.append(path, "e1", "OUTCOME", run_id="r2", outcome="WORSE")
    assert ledger.effect_of(path, "e1") == "used_harmful"
    assert ledger.summary(path)["e1"]["helpful"] == 1


def test_retrieved_but_never_applied_is_never_used(tmp_path):
    path = str(tmp_path / "l.jsonl")
    ledger.append(path, "e1", "RETRIEVED", consumer="spread_policy")
    assert ledger.effect_of(path, "e1") == "never_used"
