#!/usr/bin/env python3
"""Tests for the REVISE transition: the third one lifecycle.py promised and did not have.

WHY THIS EXISTS
    lifecycle.py's docstring lists three transitions - RETIRE, REVISE, KEEP - and only two
    were implemented. REVISE is the one that matters in the case that actually occurs: the
    entry is not harmful (so RETIRE is wrong) and it is not fine (so KEEP is wrong) because
    the record is narrower than what has since been measured about it.

    measured_families is a SNAPSHOT taken at activation. A later measurement can outgrow it,
    and then the live entry is narrower than its own evidence: retrieval withholds the
    lesson from families it demonstrably fixes. The measurement is right and the record is
    out of date - which is exactly what a revision is for.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))

import ledger  # noqa: E402
import lifecycle  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402

ACCEPTANCE = os.path.join(WT, "setup", "acceptance")
SOURCE = "HO-90899d657e68"
RECORDS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                       "records_v2.jsonl")


def _entry(**kw):
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


def _store(tmp_path, entry):
    s = tmp_path / "s.jsonl"
    l = tmp_path / "l.jsonl"
    store.append(str(s), entry)
    return str(s), str(l)


# ---------------------------------------------------------------- staleness

def test_a_narrow_record_is_stale():
    entry = _entry(measured_families=[])
    scope = lifecycle.stale_scope(entry, acceptance=ACCEPTANCE, source_task=SOURCE)
    assert scope["stale"] is True
    assert "T03_ordered" in scope["added"]


def test_a_current_record_is_not_stale():
    entry = _entry(measured_families=["T03_ordered", "T12_triple_revisit"])
    scope = lifecycle.stale_scope(entry, acceptance=ACCEPTANCE, source_task=SOURCE)
    assert scope["stale"] is False
    assert scope["added"] == []


def test_a_consumer_with_no_binding_is_NOT_reported_stale():
    """The instrument saying it cannot see an entry is a blind spot, not staleness.
    Revising on a blind spot would edit a record on the strength of nothing."""
    entry = _entry(consumer="harness", action_kind="harness_config",
                   effect_spec={"fixture": "t05_dds_harness", "operator": "harness_capacity",
                                "params": {"participant_capacity": 120}})
    scope = lifecycle.stale_scope(entry, acceptance=ACCEPTANCE, source_task=SOURCE)
    assert scope["stale"] is False
    assert "cannot see" in scope["why"]


# ---------------------------------------------------------------- the transition

def test_revise_widens_the_scope_and_appends(tmp_path):
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    successor = lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                                 acceptance=ACCEPTANCE, source_task=SOURCE)
    assert set(successor["measured_families"]) == {"T03_ordered", "T12_triple_revisit"}
    assert successor["version"]["status"] == "ACTIVE"
    assert successor["version"]["parent_entry_id"] == entry["entry_id"]


def test_a_revision_does_not_alter_the_lesson(tmp_path):
    """A revision that could rewrite the lesson would be a second, unreviewed activation
    wearing a version bump."""
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    successor = lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                                 acceptance=ACCEPTANCE, source_task=SOURCE)
    for key in ("suggested_action", "applicable_when", "known_invalid_when",
                "action_kind", "consumer", "task_family", "effect_spec"):
        assert successor[key] == entry[key], key


def test_the_previous_version_stays_on_disk(tmp_path):
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                     acceptance=ACCEPTANCE, source_task=SOURCE)
    assert any(r["entry_id"] == entry["entry_id"] for r in store.read(s))


def test_the_chain_still_verifies_after_a_revision(tmp_path):
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                     acceptance=ACCEPTANCE, source_task=SOURCE)
    assert store.verify_chain(s)[0] is True


def test_revising_a_current_entry_is_refused(tmp_path):
    entry = _entry(measured_families=["T03_ordered", "T12_triple_revisit"])
    s, l = _store(tmp_path, entry)
    with pytest.raises(schema.EntryError) as exc:
        lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                         acceptance=ACCEPTANCE, source_task=SOURCE)
    assert "nothing to revise" in str(exc.value)


def test_only_an_ACTIVE_entry_can_be_revised(tmp_path):
    entry = _entry(measured_families=[], version={"label": "E", "status": "CANDIDATE"})
    s, l = _store(tmp_path, entry)
    with pytest.raises(schema.EntryError) as exc:
        lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                         acceptance=ACCEPTANCE, source_task=SOURCE)
    assert "only an ACTIVE entry" in str(exc.value)


def test_revised_is_a_transition_not_an_outcome():
    """Counting a revision as helpful use would credit an entry for a bookkeeping change."""
    assert "REVISED" in ledger.EVENTS
    assert "REVISED" not in ledger.OUTCOMES


# ---------------------------------------------------------------- the review

def test_review_reports_REVISE_only_when_asked_to_measure(tmp_path):
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    plain = lifecycle.review(s, l)
    assert plain[0]["decision"] == "KEEP"
    assert plain[0]["scope"] is None, "an unevaluated branch must not claim 'not stale'"
    measured = lifecycle.review(s, l, measure=True, acceptance=ACCEPTANCE,
                                source_task=SOURCE)
    assert measured[0]["decision"] == "REVISE"


def test_harm_outranks_staleness(tmp_path):
    """An entry that made a run worse is retired whatever its scope says: a wider scope
    makes harm worse, not better."""
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    ledger.append(l, entry["entry_id"], "APPLIED", run_id="r", consumer="executor_recovery",
                  changed=True, detail={"why": "test"}, recorded_by="t")
    ledger.append(l, entry["entry_id"], "OUTCOME", run_id="r", consumer="executor_recovery",
                  outcome="WORSE", detail="test", recorded_by="t")
    decisions = lifecycle.review(s, l, measure=True, acceptance=ACCEPTANCE,
                                 source_task=SOURCE)
    assert decisions[0]["decision"] == "RETIRE"


# ---------------------------------------------------------------- the other direction

def test_a_record_WIDER_than_its_measurement_is_stale():
    """The worse direction, and the one the first version of this check missed.

    A record narrower than its evidence costs a missed reuse. A record WIDER than its
    evidence applies the lesson to a family nothing was measured on - and retrieval acts on
    the claim, so an over-claim becomes a wrong action.
    """
    entry = _entry(measured_families=["T03_ordered", "T12_triple_revisit", "T99_bogus"])
    scope = lifecycle.stale_scope(entry, acceptance=ACCEPTANCE, source_task=SOURCE)
    assert scope["stale"] is True
    assert scope["direction"] == "wider_than_measurement"
    assert scope["unconfirmed"] == ["T99_bogus"]


def test_a_revision_REMOVES_a_family_the_measurement_cannot_confirm(tmp_path):
    """Revision must be able to narrow. One that could only widen leaves an over-claim
    in place forever."""
    entry = _entry(measured_families=["T03_ordered", "T12_triple_revisit", "T99_bogus"])
    s, l = _store(tmp_path, entry)
    successor = lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                                 acceptance=ACCEPTANCE, source_task=SOURCE)
    assert "T99_bogus" not in successor["measured_families"]
    assert successor["version"]["revised_removed"] == ["T99_bogus"]
    assert successor["version"]["revised_direction"] == "wider_than_measurement"


def test_both_directions_can_be_true_at_once():
    """A record can under-claim one family and over-claim another. An if/elif reports only
    the first it checks, revises, and leaves the other in place."""
    entry = _entry(measured_families=["T99_bogus"])
    scope = lifecycle.stale_scope(entry, acceptance=ACCEPTANCE, source_task=SOURCE)
    assert scope["direction"] == "both_directions"
    assert "T03_ordered" in scope["added"]
    assert scope["unconfirmed"] == ["T99_bogus"]


def test_a_both_directions_revision_fixes_both(tmp_path):
    entry = _entry(measured_families=["T99_bogus"])
    s, l = _store(tmp_path, entry)
    successor = lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                                 acceptance=ACCEPTANCE, source_task=SOURCE)
    assert "T99_bogus" not in successor["measured_families"]
    assert set(successor["measured_families"]) == {"T03_ordered", "T12_triple_revisit"}


def test_the_entrys_own_family_is_not_an_over_claim():
    """task_family says where it was LEARNED; a lesson need not still fix its source
    instance, so counting that as an over-claim would revise every honest entry."""
    entry = _entry(measured_families=["T03_ordered", "T12_triple_revisit"])
    scope = lifecycle.stale_scope(entry, acceptance=ACCEPTANCE, source_task=SOURCE)
    assert scope["stale"] is False
    assert "T13_geometric_conditional" in scope["recorded"]


def test_the_direction_is_reported_because_the_two_differ():
    narrow = lifecycle.stale_scope(_entry(measured_families=[]),
                                   acceptance=ACCEPTANCE, source_task=SOURCE)
    wide = lifecycle.stale_scope(
        _entry(measured_families=["T03_ordered", "T12_triple_revisit", "T99_bogus"]),
        acceptance=ACCEPTANCE, source_task=SOURCE)
    assert narrow["direction"] == "narrower_than_measurement"
    assert wide["direction"] == "wider_than_measurement"
    assert narrow["direction"] != wide["direction"]


# ---------------------------------------------------------------- apply() must act

def test_apply_carries_out_a_REVISE_not_only_a_RETIRE(tmp_path):
    """apply() looped over {"RETIRE"} only, so a review that said REVISE changed nothing:
    a loop whose action half ignores half its own findings."""
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    result = lifecycle.apply(s, l, acceptance=ACCEPTANCE, source_task=SOURCE, measure=True)
    assert len(result["revised"]) == 1
    assert result["retired"] == []
    after = [r for r in store.read(s) if r["version"]["status"] == "ACTIVE"
             and r.get("measured_families")]
    assert after, "apply() reported a revision but the store gained none"


def test_apply_is_idempotent_for_a_revision(tmp_path):
    """A second pass must not revise the same entry again."""
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    lifecycle.apply(s, l, acceptance=ACCEPTANCE, source_task=SOURCE, measure=True)
    second = lifecycle.apply(s, l, acceptance=ACCEPTANCE, source_task=SOURCE, measure=True)
    assert second["revised"] == []


def test_apply_without_measure_revises_nothing(tmp_path):
    """The revision branch is not evaluated unless asked, so it cannot fire on a
    ledger-only review."""
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    result = lifecycle.apply(s, l)
    assert result["revised"] == []


def test_a_revised_entry_is_no_longer_stale(tmp_path):
    """It must SETTLE. A transition that re-fires on its own output is a loop, not a fix."""
    entry = _entry(measured_families=[])
    s, l = _store(tmp_path, entry)
    lifecycle.revise(entry["entry_id"], store_path=s, ledger_path=l,
                     acceptance=ACCEPTANCE, source_task=SOURCE)
    after = lifecycle.review(s, l, measure=True, acceptance=ACCEPTANCE,
                             source_task=SOURCE)
    assert [d["decision"] for d in after if d["decision"] == "REVISE"] == []
