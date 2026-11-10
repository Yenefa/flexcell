#!/usr/bin/env python3
"""Tests for the failure -> proposal loop.

THE GAP THESE GUARD: evolution/proposals/ was an EMPTY directory. regress.py could gate
a proposal but nothing produced one, so no proposal could ever be accepted and C could
never change itself - which is exactly why two B/C experiments measured zero effect.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evolution" / "validation"))
import regress

# Load the generator by PATH: a plain "import generate" resolves to
# benchmark/generators/generate.py, which is the task generator, not this one. The first
# version of this test silently exercised the wrong module.
import importlib.util


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


generate = _load("evobot_proposal_generate",
                 ROOT / "evolution" / "proposals" / "generate.py")
check_applied = _load("evobot_proposal_check",
                      ROOT / "evolution" / "proposals" / "check_applied.py")


def _f(detail, code=60):
    return {"run": "x", "error_code": code, "detail": detail,
            "completed_stage_ids": []}


def test_cluster_groups_by_observable_signature_only():
    buckets = generate.cluster([
        _f("declared destination occupied at a-0"),
        _f("state drift or occupied destination before b-1"),
        _f("native terminal/verification unconfirmed for a-0"),
    ])
    assert len(buckets["occupied_destination"]) == 2
    assert len(buckets["unconfirmed"]) == 1


def test_thin_evidence_is_refused():
    proposal, why = generate.build_proposal("occupied_destination", [_f("occupied destination")])
    assert proposal is None
    assert "need" in why


def test_unknown_signature_is_refused_not_invented():
    proposal, why = generate.build_proposal(
        "unconfirmed", [_f("unconfirmed for a-0")] * 19)
    assert proposal is None
    assert "no evidence-backed change" in why


def test_a_real_proposal_passes_the_existing_gate():
    fs = [_f("declared destination occupied")] * 5
    proposal, _ = generate.build_proposal("occupied_destination", fs)
    assert proposal is not None
    ok, reason = regress.gate(proposal, run_regressions=False)
    assert ok, reason
    assert proposal["requires_human_approval"] is True


def test_generator_cannot_propose_touching_a_protected_path():
    fs = [_f("declared destination occupied")] * 5
    proposal, _ = generate.build_proposal("occupied_destination", fs)
    proposal = dict(proposal, files=["benchmark/evaluators/evaluate.py"])
    ok, reason = regress.gate(proposal, run_regressions=False)
    assert ok is False
    assert "protected" in reason


def test_generated_proposal_is_truthfully_labelled_retrospective_or_would_fix():
    """The check must call an already-satisfied change what it is."""
    label, why = check_applied.check_occupied_destination()
    assert label in ("ALREADY_SATISFIED", "WOULD_FIX", "REFUSED")
    # the spacing change is already in the code, so this must NOT claim a new discovery
    assert label == "ALREADY_SATISFIED", (label, why)

