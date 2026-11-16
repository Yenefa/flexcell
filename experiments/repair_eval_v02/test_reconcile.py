"""Tests for the manifest/record reconciliation.

The case that matters most is the one that never happens on purpose: a dry-run
record promoting a slot. Everything here exists so that cannot pass silently.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import reconcile as RC  # noqa: E402

MANIFEST = ROOT / "docs" / "research" / "evobot-paper-v02" / "RUN_MANIFEST.md"


def two_slots(status_a="NOT_RUN", status_b="NOT_RUN"):
    return {"F1-A-r1": status_a, "F1-B-r1": status_b}


def record(slot_id, status, qualification="REAL"):
    return {"slot_id": slot_id, "terminal_status": status,
            "qualification": qualification}


# ------------------------------------------------------------- the parser
def test_the_manifest_parses_into_the_24_slots():
    statuses = RC.parse_manifest(MANIFEST)
    assert len(statuses) == 24
    assert set(statuses.values()) == {"NOT_RUN"}


def test_every_manifest_status_is_in_the_vocabulary():
    statuses = RC.parse_manifest(MANIFEST)
    for slot, status in statuses.items():
        assert status in RC.KNOWN_STATUSES, (slot, status)


# --------------------------------------------- the case that must not pass
def test_a_dry_run_record_cannot_promote_a_slot():
    """The whole point. A DRY_RUN record must never turn NOT_RUN into terminal."""
    statuses = two_slots()
    records = [record("F1-A-r1", "SUCCESS_VERIFIED", qualification="DRY_RUN")]
    report = RC.reconcile(statuses, records)
    assert report["consistent"] is True
    assert report["excluded_not_real"] == ["F1-A-r1"]
    assert statuses["F1-A-r1"] == "NOT_RUN"


def test_a_scripted_transport_record_is_excluded_too():
    statuses = two_slots()
    records = [record("F1-A-r1", "SUCCESS_VERIFIED",
                      qualification="SCRIPTED_TRANSPORT_NOT_A_MODEL_RESULT")]
    report = RC.reconcile(statuses, records)
    assert report["excluded_not_real"] == ["F1-A-r1"]
    assert report["consistent"] is True


def test_the_exclusion_is_reported_rather_than_silent():
    statuses = two_slots()
    records = [record("F1-A-r1", "SUCCESS_VERIFIED", qualification="DRY_RUN")]
    report = RC.reconcile(statuses, records)
    assert report["excluded_not_real"], "an excluded record must stay visible"


# ------------------------------------------------------------- drift both ways
def test_a_real_record_that_promotes_a_not_run_slot_is_drift():
    statuses = two_slots()
    records = [record("F1-A-r1", "SUCCESS_VERIFIED")]
    report = RC.reconcile(statuses, records)
    assert report["consistent"] is False
    assert any("NOT_RUN" in d for d in report["drift"])


def test_a_terminal_slot_with_no_record_behind_it_is_drift():
    statuses = two_slots(status_a="SUCCESS_VERIFIED")
    report = RC.reconcile(statuses, [])
    assert report["consistent"] is False
    assert any("no real record backs it" in d for d in report["drift"])


def test_a_status_disagreement_is_drift():
    statuses = two_slots(status_a="FAIL")
    records = [record("F1-A-r1", "SUCCESS_VERIFIED")]
    report = RC.reconcile(statuses, records)
    assert report["consistent"] is False
    assert any("manifest says FAIL" in d for d in report["drift"])


def test_agreement_is_consistent():
    statuses = two_slots(status_a="FAIL")
    records = [record("F1-A-r1", "FAIL")]
    report = RC.reconcile(statuses, records)
    assert report["consistent"] is True
    assert report["drift"] == []


# --------------------------------------------------------- structural refusals
def test_a_record_for_an_unlisted_slot_is_refused():
    with pytest.raises(RC.ReconcileError):
        RC.reconcile(two_slots(), [record("F9-Z-r9", "FAIL")])


def test_two_real_records_on_one_slot_are_refused():
    with pytest.raises(RC.ReconcileError):
        RC.reconcile(two_slots(), [record("F1-A-r1", "FAIL"),
                                   record("F1-A-r1", "FAIL")])


def test_a_status_outside_the_vocabulary_is_refused():
    with pytest.raises(RC.ReconcileError):
        RC.reconcile(two_slots(), [record("F1-A-r1", "PASSED")])


def test_a_manifest_status_outside_the_vocabulary_is_refused(tmp_path):
    bad = tmp_path / "m.md"
    bad.write_text("| 1 | `F1-A-r1` | F1 | x | A | r1 | s | - | b | `PASSED` |" + chr(10),
                   encoding="utf-8")
    with pytest.raises(RC.ReconcileError):
        RC.parse_manifest(bad)


# ------------------------------------------------------- against the real files
def test_the_checked_in_manifest_has_no_records_yet_and_that_is_consistent():
    statuses = RC.parse_manifest(MANIFEST)
    report = RC.assert_reconciled(statuses, [])
    assert report["manifest_slots"] == 24
    assert report["records"] == 0


def test_the_dry_run_matrix_records_are_all_excluded():
    """The evidence the matrix actually produced must not move a single slot."""
    evidence = ROOT / "experiments" / "repair_eval_v02" / "evidence" / "budget_matrix.json"
    if not evidence.exists():
        pytest.skip("matrix evidence not generated in this checkout")
    records = RC.load_records(evidence)
    assert len(records) == 24
    statuses = RC.parse_manifest(MANIFEST)
    report = RC.reconcile(statuses, records)
    assert len(report["excluded_not_real"]) == 24
    assert report["consistent"] is True
    assert set(statuses.values()) == {"NOT_RUN"}
