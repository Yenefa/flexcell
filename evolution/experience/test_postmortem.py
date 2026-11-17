#!/usr/bin/env python3
"""Tests for the generator: archived failure -> entry candidate, with no self-review.

WHY THESE CASES
    An automatic generator is where a pipeline can quietly start lying:
      * it can emit entries whose effect was never runnable ("asserted, not measured");
      * it can emit entries with a disclaimer no probe covers (UNPROBED downstream);
      * it can set ACCEPT itself, which would make every downstream gate vacuous;
      * it can promote one occurrence, which this repository has already done once and
        had to retract.

    Each test below pins one of those.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import misuse  # noqa: E402
import postmortem  # noqa: E402
import schema  # noqa: E402


def failure(code=60, detail="declared destination occupied", committed=None, path="x/task.out"):
    return {"path": path, "error_code": code, "detail": detail,
            "completed_stage_ids": committed or [], "outcome": 1}


# ---------------------------------------------------------------- scanning

def test_scan_reads_measured_fields_not_prose(tmp_path):
    batch = tmp_path / "evobot_x_20260101" / "runs" / "r1"
    batch.mkdir(parents=True)
    (batch / "task.out").write_text(
        'RESULT {"outcome": 1, "error_code": 60, "detail": "declared destination '
        'occupied", "completed_stage_ids": ["a-0"]}', encoding="utf-8")
    rows = postmortem.scan(str(tmp_path))
    assert len(rows) == 1
    assert rows[0]["error_code"] == 60
    assert rows[0]["completed_stage_ids"] == ["a-0"]


def test_scan_skips_successful_runs(tmp_path):
    batch = tmp_path / "evobot_x_20260101" / "runs" / "r1"
    batch.mkdir(parents=True)
    (batch / "task.out").write_text('RESULT {"outcome": 0, "error_code": 0}',
                                    encoding="utf-8")
    assert postmortem.scan(str(tmp_path)) == []


def test_scan_skips_unparseable_output(tmp_path):
    batch = tmp_path / "evobot_x_20260101" / "runs" / "r1"
    batch.mkdir(parents=True)
    (batch / "task.out").write_text("RESULT not json", encoding="utf-8")
    assert postmortem.scan(str(tmp_path)) == []


# ---------------------------------------------------------------- generation

def test_the_real_archive_generates_the_occupied_destination_entry():
    entries, report = postmortem.generate()
    sigs = {e["version"]["label"] for e in entries}
    assert "auto-occupied_destination" in sigs, report
    assert report["scanned"] > 0


def test_the_largest_cluster_is_refused_because_nothing_can_act_on_it():
    """46 of 51 archived failures are unconfirmed_native; refusing it is the honest result."""
    entries, report = postmortem.generate()
    sig = report["signatures"]["unconfirmed_native"]
    assert sig["built"] is False
    assert "UNROUTED" in sig["why"]


def test_evidence_is_built_from_parsed_fields():
    entries, _ = postmortem.generate()
    entry = next(e for e in entries if e["version"]["label"] == "auto-occupied_destination")
    for key in ("occurrences", "error_codes", "exemplar_run"):
        assert key in entry["evidence"], entry["evidence"]
    assert isinstance(entry["evidence"]["occurrences"], int)


def test_a_generated_entry_is_never_self_reviewed():
    entries, _ = postmortem.generate()
    for entry in entries:
        assert entry["origin"] == "AGENT_GENERATED"
        assert entry["validation"]["review_verdict"] == "NOT_REVIEWED"
        assert entry["validation"]["reviewed_by"] is None
        assert entry["version"]["status"] == "CANDIDATE"


def test_a_generated_entry_passes_its_own_schema():
    entries, _ = postmortem.generate()
    assert entries
    for entry in entries:
        assert schema.validate(entry) == []


def test_a_generated_entry_is_blocked_on_its_disclaimers():
    """If it were not, activation would refuse it later and look like a review problem."""
    entries, _ = postmortem.generate()
    for entry in entries:
        result = misuse.check(entry)
        assert result["verdict"] == "BLOCKED", (entry["version"]["label"], result)


def test_one_occurrence_is_refused():
    entry, why = postmortem.build("occupied_destination", [failure()])
    assert entry is None
    assert "need 2" in why and "mis-attribution" in why


def test_an_unknown_signature_is_unrouted_not_guessed():
    entry, why = postmortem.build("mystery_signature", [failure(), failure()])
    assert entry is None
    assert "UNROUTED" in why


def test_a_signature_without_a_runnable_effect_is_not_ready(monkeypatch):
    """A spec that cannot be run would make the effect 'asserted' rather than measured."""
    monkeypatch.setitem(postmortem.SIGNATURES, "occupied_destination",
                        dict(postmortem.SIGNATURES["occupied_destination"],
                             effect_spec={"operator": "spread_step"}))
    entry, why = postmortem.build("occupied_destination", [failure(), failure()])
    assert entry is None
    assert "NOT_READY" in why and "effect_spec" in why


def test_a_signature_with_partial_probes_is_not_ready(monkeypatch):
    spec = dict(postmortem.SIGNATURES["occupied_destination"])
    spec["invalid_probes"] = spec["invalid_probes"][:1]
    monkeypatch.setitem(postmortem.SIGNATURES, "occupied_destination", spec)
    entry, why = postmortem.build("occupied_destination", [failure(), failure()])
    assert entry is None
    assert "NOT_READY" in why


def test_generation_is_deterministic():
    a, _ = postmortem.generate()
    b, _ = postmortem.generate()
    assert [e["entry_id"] for e in a] == [e["entry_id"] for e in b]
