#!/usr/bin/env python3
"""Tests for Baseline C: experience store, diagnosis, retrieval, regression gate.

All offline. The point of these tests is that C cannot manufacture success: protected
paths are refused, evidence is mandatory, and the chain detects deleted failures.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in ("evolution/experience", "evolution/diagnosis", "evolution/validation",
          "experiments/baselines", "runtime/planner"):
    sys.path.insert(0, str(ROOT / p))

import store
import classify as diag
import regress
import baseline_c as C


@pytest.fixture
def tmpstore(tmp_path):
    return tmp_path / "records.jsonl"


def _rec(task="T05", cls="runtime", lesson="Wait for the previous skill goal to be released before the next stage."):
    return store.make_record(task, cls,
                             {"error_code": 41, "detail": "another pick goal is active"},
                             lesson, "run-xyz", "failed")


def test_store_is_append_only_and_chain_verifies(tmpstore):
    store.append(tmpstore, _rec("a"))
    store.append(tmpstore, _rec("b"))
    ok, msg = store.verify_chain(tmpstore)
    assert ok, msg
    assert len(store.read(tmpstore)) == 2


def test_deleting_a_failure_record_is_detected(tmpstore):
    store.append(tmpstore, _rec("a"))
    store.append(tmpstore, _rec("b"))
    lines = tmpstore.read_text().splitlines()
    tmpstore.write_text(lines[1] + "\n")   # pretend the failure never happened
    ok, _ = store.verify_chain(tmpstore)
    assert ok is False


def test_tampering_with_a_lesson_is_detected(tmpstore):
    store.append(tmpstore, _rec())
    rows = tmpstore.read_text().splitlines()
    obj = json.loads(rows[0])
    obj["lesson"] = "pretend everything passed"
    tmpstore.write_text(json.dumps(obj) + "\n")
    ok, _ = store.verify_chain(tmpstore)
    assert ok is False


def test_duplicate_record_is_refused(tmpstore):
    r = _rec()
    store.append(tmpstore, r)
    with pytest.raises(ValueError):
        store.append(tmpstore, r)


def test_scope_guard_refuses_evaluator_or_tolerance_lessons():
    for bad in ["widen the evaluator tolerance", "lower the pass threshold",
                "change the verifier to accept it"]:
        with pytest.raises(ValueError):
            _rec(lesson=bad)


def test_diagnosis_uses_measured_evidence_not_a_story():
    assert diag.classify({"detail": "Failed to find a free participant index for domain 213"})[0] == "runtime"
    assert diag.classify({"detail": "declared destination occupied at a-1"})[0] == "planning"
    assert diag.classify({"detail": "plan must declare every observed object"})[0] == "planning"
    assert diag.classify({"detail": "another pick goal is active"})[0] == "runtime"
    assert diag.classify({"detail": "measured pose outside tolerance"})[0] == "kinematics"
    assert diag.classify({"detail": "something odd happened"})[0] == "UNKNOWN"
    assert diag.classify({})[0] == "UNKNOWN"


def test_held_out_baseline_guard_reports_intact():
    ok, why = regress.held_out_baseline_intact()
    assert ok is True, why
    assert "held-out" in why


def test_deleting_the_held_out_baseline_is_refused(monkeypatch, tmp_path):
    """Regression: a missing baseline used to pass the guard, which made evidence
    deletion a way around the gate."""
    monkeypatch.setattr(regress, "HELD_OUT_BASELINE", tmp_path / "gone")
    ok, why = regress.held_out_baseline_intact()
    assert ok is False
    assert "missing" in why
    accepted, reason = regress.gate(
        {"files": ["runtime/planner/agent_planner.py"], "evidence": {"e": 1},
         "expected_effect": "x", "rollback": "revert"}, run_regressions=False)
    assert accepted is False
    assert "missing" in reason



def test_regression_gate_refuses_protected_paths():
    for f in ["benchmark/evaluators/evaluate.py",
              "benchmark/schemas/taskspec.schema.json",
              "/etc/evobot/sealed/HO-abc.json"]:
        ok, why = regress.gate({"files": [f], "evidence": {"x": 1},
                                "expected_effect": "x", "rollback": "revert"},
                               run_regressions=False)
        assert ok is False, (f, why)


def test_regression_gate_requires_evidence_effect_and_rollback():
    base = {"files": ["runtime/planner/agent_planner.py"]}
    ok, _ = regress.gate(base, run_regressions=False)
    assert ok is False
    base["evidence"] = {"error_code": 41}
    ok, _ = regress.gate(base, run_regressions=False)
    assert ok is False
    base["expected_effect"] = "planner waits at stage handover"
    ok, _ = regress.gate(base, run_regressions=False)
    assert ok is False
    base["rollback"] = "git checkout runtime/planner/agent_planner.py"
    ok, why = regress.gate(base, run_regressions=False)
    assert ok is True, why


def test_retrieval_refuses_a_broken_chain(tmpstore, tmp_path):
    store.append(tmpstore, _rec())
    rows = tmpstore.read_text().splitlines()[0]
    tmpstore.write_text(rows + "\n")
    store.append(tmpstore, _rec("b", lesson="right bin is at negative y"))
    # chain is intact here; break it by removing record 1
    lines = tmpstore.read_text().splitlines()
    tmpstore.write_text(lines[1] + "\n")
    obs = {"instruction": "put it in the right bin"}
    with pytest.raises(RuntimeError):
        C.retrieve(obs, tmpstore)


def test_only_validated_records_are_retrieved(tmpstore):
    rec = _rec(lesson="right bin is at negative y")
    store.append(tmpstore, rec)
    obs = {"instruction": "put it in the right bin"}
    assert C.retrieve(obs, tmpstore) == []   # not validated yet


def test_enrichment_does_not_mutate_the_observation(tmpstore):
    rec = _rec(lesson="right bin is at negative y")
    rec["validated"] = True
    rec["record_sha256"] = store._hash({k: v for k, v in rec.items() if k != "record_sha256"})
    store.append(tmpstore, rec)
    obs = {"instruction": "put it in the right bin", "objects": [], "zones": [], "skills": []}
    before = json.dumps(obs, sort_keys=True)
    enriched = C.build_observation_with_experience(obs, tmpstore)
    assert json.dumps(obs, sort_keys=True) == before
    assert "experience" in enriched
