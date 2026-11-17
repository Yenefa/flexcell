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

def test_the_dev_split_honestly_produces_nothing():
    """T12/T13 exist ONLY in the held-out set, so the dev split has no lesson to offer.

    This is the finding, not a regression: reporting zero here is correct, and the first
    version of this generator only appeared to work because it was quietly reading the
    held-out measurement batches.
    """
    entries, report = postmortem.generate()
    assert report["split"] == "dev"
    assert entries == []
    assert report["held_out_would_exclude"] > 0


def test_the_held_out_split_generates_the_entry_and_labels_it():
    entries, report = postmortem.generate(split="held_out")
    labels = {e["version"]["label"] for e in entries}
    assert "auto-occupied_destination" in labels, report
    for entry in entries:
        assert entry["evidence"]["evidence_split"] == "held_out"
        assert "HELD-OUT" in entry["notes"]


def test_a_held_out_entry_still_says_so_after_activation(tmp_path):
    """The label must survive activation, or the caveat dies at the first status change."""
    import curate
    import store as store_mod
    entries, _ = postmortem.generate(split="held_out")
    entry = entries[0]
    s, l = tmp_path / "s.jsonl", tmp_path / "l.jsonl"
    store_mod.append(str(s), entry)
    succ = curate.activate(entry["entry_id"],
                           {"review_verdict": "ACCEPT", "reviewed_by": "r"},
                           store_path=str(s), ledger_path=str(l))
    assert succ["evidence"]["evidence_split"] == "held_out"


def test_the_largest_cluster_is_refused_because_nothing_can_act_on_it():
    """46 of 51 archived failures are unconfirmed_native; refusing it is the honest result."""
    entries, report = postmortem.generate()
    sig = report["signatures"]["unconfirmed_native"]
    assert sig["built"] is False
    assert "UNROUTED" in sig["why"]


def test_evidence_is_built_from_parsed_fields():
    entries, _ = postmortem.generate(split="held_out")
    entry = next(e for e in entries if e["version"]["label"] == "auto-occupied_destination")
    for key in ("occurrences", "error_codes", "exemplar_run"):
        assert key in entry["evidence"], entry["evidence"]
    assert isinstance(entry["evidence"]["occurrences"], int)


def test_a_generated_entry_is_never_self_reviewed():
    entries, _ = postmortem.generate(split="held_out")
    for entry in entries:
        assert entry["origin"] == "AGENT_GENERATED"
        assert entry["validation"]["review_verdict"] == "NOT_REVIEWED"
        assert entry["validation"]["reviewed_by"] is None
        assert entry["version"]["status"] == "CANDIDATE"


def test_a_generated_entry_passes_its_own_schema():
    entries, _ = postmortem.generate(split="held_out")
    assert entries
    for entry in entries:
        assert schema.validate(entry) == []


def test_a_generated_entry_is_blocked_on_its_disclaimers():
    """If it were not, activation would refuse it later and look like a review problem."""
    entries, _ = postmortem.generate(split="held_out")
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
    a, _ = postmortem.generate(split="held_out")
    b, _ = postmortem.generate(split="held_out")
    assert [e["entry_id"] for e in a] == [e["entry_id"] for e in b]


# ---------------------------------------------------------------- held-out exclusion
#
# The first version of scan() globbed EVERY archived batch. The one entry it produced
# drew one of its five occurrences from evobot_unseen_n6_20261111 - a batch whose whole
# purpose was to MEASURE generalization. An experience partly learned from the measuring
# instrument cannot afterwards be cited as evidence that the agent generalizes: the
# instrument has been read into the thing it measures.

def test_held_out_batches_are_derived_not_hand_listed():
    """A new held-out batch must be excluded the moment it is indexed."""
    batches = postmortem.held_out_batches()
    assert "evobot_unseen_n6_20261111" in batches
    assert "evobot_heldout_n6_20261111" in batches
    assert "evobot_unseen_bc_20261111" in batches
    # a development batch must NOT be excluded, or the generator would starve
    assert "evobot_recover_n6_20261111" not in batches


def test_scan_excludes_every_held_out_batch():
    rows = postmortem.scan()
    held = postmortem.held_out_batches()
    leaked = {r["path"].split(os.sep)[0] for r in rows} & held
    assert leaked == set(), "generator read held-out batches: %s" % sorted(leaked)


def test_the_report_says_what_was_excluded_and_why():
    _, report = postmortem.generate()
    assert report["excluded_held_out"], "no exclusion reported"
    assert sum(report["excluded_held_out"].values()) > 0
    assert report["held_out_batches"]


def test_the_dev_split_never_cites_a_held_out_file():
    """The dev split's own output (empty here) must never cite held-out evidence."""
    entries, report = postmortem.generate()
    held = set(report["held_out_batches"])
    for entry in entries:
        for path in entry.get("evidence_files") or []:
            assert path.split(os.sep)[0] not in held, (entry["version"]["label"], path)
        assert entry["source_run"].split(os.sep)[0] not in held


def test_asking_for_held_out_data_is_possible_but_explicit():
    """The exclusion is a default, not a hidden rule: a caller can override it."""
    rows, excluded = postmortem.scan_with_report(include_held_out=True)
    assert excluded == {}
    assert any(r["path"].split(os.sep)[0] in postmortem.held_out_batches()
               for r in rows)


def test_the_sealed_instance_criterion_can_actually_fire(tmp_path, monkeypatch):
    """The second criterion must be able to reject, or it is decoration.

    A labelled batch list goes stale; the sealed-instance check is the one that survives
    a mislabelled batch. This drives it through both states on a synthetic tree: first
    with a sealed id in the path (must be excluded), then with an ordinary id (must not).
    """
    sealed = {"HO-aaaaaaaaaaaa"}
    monkeypatch.setattr(postmortem, "sealed_instances", lambda: sealed)
    monkeypatch.setattr(postmortem, "held_out_batches", lambda: set())

    def write(run, text):
        d = tmp_path / "evobot_dev_20260101" / "runs" / run
        d.mkdir(parents=True)
        (d / "task.out").write_text(text, encoding="utf-8")

    body = ('RESULT {"outcome": 1, "error_code": 60, '
            '"detail": "declared destination occupied"}')
    write("HO-aaaaaaaaaaaa", body)
    write("HO-bbbbbbbbbbbb", body)
    rows, excluded = postmortem.scan_with_report(str(tmp_path))
    assert [r["path"].split(os.sep)[-2] for r in rows] == ["HO-bbbbbbbbbbbb"]
    assert any("sealed_instance" in k for k in excluded), excluded


def test_cites_sealed_is_false_when_nothing_is_sealed():
    """An empty held-out set must not exclude everything by accident."""
    assert postmortem.cites_sealed("runs/HO-aaaaaaaaaaaa/task.out", set()) is False
