#!/usr/bin/env python3
"""Tests for native-diagnostics enrichment.

Regression for a real dead end: six runs failed with a generic composite err 62 and the
classifier correctly answered UNKNOWN, so the runner declined to act. The information
needed to attribute them was already in the composite journal.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "recovery"))
sys.path.insert(0, str(ROOT / "evolution" / "diagnosis"))
import diagnostics
import classify


def _journal(tmp_path, rows):
    d = tmp_path / "sim" / "skills" / "composites"
    d.mkdir(parents=True)
    p = d / "composite-test.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return tmp_path


def test_place_failure_is_extracted_from_the_journal(tmp_path):
    run = _journal(tmp_path, [
        {"event": "PLAN"},
        {"event": "NATIVE_TERMINAL", "stage_id": "a-0",
         "component": {"outcome": 1, "error_code": 50,
                       "detail": "policy abort: place failed (ERR_PLACE_FAILED)",
                       "final_state": {"fsm_trace": ["PICK_A(attempt=1):OK", "PLACE_A:FAIL"],
                                       "object_at_place": False}}},
    ])
    st = diagnostics.failure_trace(str(run))
    assert st is not None
    assert st["fsm_trace"] == ["PICK_A(attempt=1):OK", "PLACE_A:FAIL"]


def test_enrichment_turns_unknown_into_an_attributable_class(tmp_path):
    run = _journal(tmp_path, [
        {"event": "NATIVE_TERMINAL", "stage_id": "a-0",
         "component": {"outcome": 1, "error_code": 50,
                       "detail": "place failed",
                       "final_state": {"fsm_trace": ["PICK_A:OK", "PLACE_A:FAIL"]}}},
    ])
    base = {"outcome": 1, "error_code": 62,
            "detail": "native terminal/verification unconfirmed",
            "completed_stage_ids": []}
    assert classify.classify(base)[0] == "UNKNOWN"
    enriched = diagnostics.enrich(base, str(run))
    assert classify.classify(enriched)[0] == "grasp"
    assert enriched["error_code"] == 62   # the composite code is preserved


def test_enrichment_never_mutates_the_input_evidence(tmp_path):
    run = _journal(tmp_path, [
        {"event": "NATIVE_TERMINAL", "stage_id": "a-0",
         "component": {"outcome": 1, "error_code": 50, "detail": "place failed",
                       "final_state": {"fsm_trace": ["PLACE_A:FAIL"]}}},
    ])
    base = {"error_code": 62, "detail": "unconfirmed", "completed_stage_ids": []}
    before = json.dumps(base, sort_keys=True)
    diagnostics.enrich(base, str(run))
    assert json.dumps(base, sort_keys=True) == before


def test_missing_journal_yields_no_invented_diagnostics(tmp_path):
    base = {"error_code": 62, "detail": "unconfirmed", "completed_stage_ids": []}
    enriched = diagnostics.enrich(base, str(tmp_path))
    assert enriched == base
    assert classify.classify(enriched)[0] == "UNKNOWN"


def test_pick_failure_is_attributed_to_grasp(tmp_path):
    run = _journal(tmp_path, [
        {"event": "NATIVE_TERMINAL", "stage_id": "a-0",
         "component": {"outcome": 1, "error_code": 50, "detail": "pick failed",
                       "final_state": {"fsm_trace": ["PICK_A:FAIL"]}}},
    ])
    enriched = diagnostics.enrich({"error_code": 62, "detail": "unconfirmed",
                                   "completed_stage_ids": []}, str(run))
    cls, why = classify.classify(enriched)
    assert cls == "grasp"
    assert "pick" in why

