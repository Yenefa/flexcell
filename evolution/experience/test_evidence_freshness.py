#!/usr/bin/env python3
"""Tests for evidence freshness: is the committed run still what the code produces?

WHY THIS EXISTS
    verify.py regenerates the chain into a TEMP directory and asserts properties of THAT
    run. That checks the code is self-consistent; it does not check that the artifacts
    committed under setup/acceptance/evobot_continual_chain_20261118/ still describe the
    code. They had already diverged - 18 of 32 files recorded a chain the current code no
    longer produces - and nothing said so.

    The root cause is worth pinning separately: the entry body embedded an ABSOLUTE output
    path (review_ref), and entry_id is a digest of the body, so an entry's identity depended
    on WHERE the demo ran. A committed artifact set could therefore never match a fresh run,
    which made any freshness check impossible until that was fixed.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))

import demo_continual  # noqa: E402
import evidence_freshness  # noqa: E402


# ---------------------------------------------------------------- the comparison rules

def test_identity_fields_are_not_compared_as_numbers():
    """A digest is not a measurement; counting it as one would fail on every change."""
    old = {"entry_id": "a" * 64, "n": 7, "reviewed_by": "r", "ran_at": "2026-11-18"}
    assert evidence_freshness._numbers(old) == {"/n": 7}


def test_booleans_are_not_numbers():
    assert evidence_freshness._numbers({"ok": True}) == {}


def test_cited_numbers_are_found_at_any_depth():
    doc = {"a": [{"b": 3}, {"c": 4.5}], "d": {"e": {"f": 6}}}
    assert evidence_freshness._numbers(doc) == {"/a[0]/b": 3, "/a[1]/c": 4.5,
                                                "/d/e/f": 6}


def test_the_claim_says_churn_is_age_not_failure(fresh_report):
    assert "age" in fresh_report["claim"].lower()
    assert "switched off" in fresh_report["claim"]


# ---------------------------------------------------------------- the real evidence

@pytest.fixture(scope="module")
def fresh_run(tmp_path_factory):
    """ONE regenerated run for the whole module. Each demo run takes ~25 s, and running it
    per test made this file the slowest in the suite for no extra coverage."""
    return evidence_freshness.regenerate(str(tmp_path_factory.mktemp("fresh")))


@pytest.fixture(scope="module")
def fresh_report(fresh_run):
    return evidence_freshness.compare(fresh_dir=fresh_run)


def test_the_committed_evidence_numbers_do_not_drift(fresh_report):
    assert fresh_report["number_drift"] == [], fresh_report["number_drift"][:3]


def test_the_committed_evidence_ids_do_not_drift(fresh_report):
    """Only possible because review_ref stopped carrying the run directory."""
    assert fresh_report["id_churn"] == [], fresh_report["id_churn"][:5]


def test_every_committed_artifact_is_still_produced(fresh_report):
    assert fresh_report["missing"] == []


def test_a_stale_number_is_reported(tmp_path, fresh_run):
    """The check must be able to FAIL, or it is decoration."""
    fresh = fresh_run
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    src = os.path.join(evidence_freshness.EVIDENCE, "SUMMARY.json")
    doc = json.load(open(src, encoding="utf-8"))
    # perturb a cited number
    doc["measured_result"] = dict(doc.get("measured_result") or {}, tampered=12345)
    (evidence / "SUMMARY.json").write_text(json.dumps(doc), encoding="utf-8")
    report = evidence_freshness.compare(fresh_dir=fresh, evidence=str(evidence))
    assert any(d["file"] == "SUMMARY.json" for d in report["number_drift"])


def test_an_artifact_the_demo_no_longer_produces_is_reported(tmp_path, fresh_run):
    fresh = fresh_run
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "99_obsolete.json").write_text("{}", encoding="utf-8")
    report = evidence_freshness.compare(fresh_dir=fresh, evidence=str(evidence))
    assert any(m["file"] == "99_obsolete.json" for m in report["missing"])


# ---------------------------------------------------------------- entry identity

def test_an_entry_id_does_not_depend_on_where_the_demo_ran(tmp_path):
    """review_ref used to be an ABSOLUTE path built from the output directory, and it is
    part of the entry body - so the same chain written to two places got two identities."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    demo_continual.run(str(a))
    demo_continual.run(str(b))
    ids_a = [json.loads(line)["entry_id"]
             for line in (a / "records_v2.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()]
    ids_b = [json.loads(line)["entry_id"]
             for line in (b / "records_v2.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()]
    assert ids_a == ids_b


def test_a_review_ref_resolves_to_a_file_that_exists(tmp_path):
    """It used to point outside the run directory at a file nothing wrote."""
    demo_continual.run(str(tmp_path))
    for line in (tmp_path / "records_v2.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ref = (json.loads(line).get("validation") or {}).get("review_ref")
        if ref:
            assert not os.path.isabs(ref), ref
            assert (tmp_path / ref).exists(), ref
