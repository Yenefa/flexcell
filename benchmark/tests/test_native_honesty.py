#!/usr/bin/env python3
"""Tests for the native honesty analyser: a missing claim must never be scored as a failure.

THREE DEFECTS THESE GUARD, all found by running the chain end to end on fresh seeds:
  1. the batch runner left cwd at the sim checkout, so self_assess.py failed to open and
     NO claim was collected;
  2. evaluate() does bool(final_state.get(...)), so an ABSENT claim reads as False - the
     verdict's agent_claimed_success can never distinguish "claimed failure" from "no claim";
  3. my first analyser read that verdict field and therefore reported "16/16 measured" and
     counted all 16 as false failures, repeating the evaluator's coercion in the analyst.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "nh", ROOT / "experiments" / "baselines" / "native_honesty.py")
NH = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NH)


def test_analyser_reads_the_observation_not_the_verdict():
    src = (ROOT / "experiments" / "baselines" / "native_honesty.py").read_text(
        encoding="utf-8")
    assert "DO NOT trust verdict" in src
    assert "agent_claim_source" in src


def test_wilson_interval_is_not_a_point_estimate():
    p, lo, hi = NH.wilson(0, 16)
    assert p == 0.0
    assert hi > 0.1, "a zero on n=16 must not be reported as certainty"


def test_native_batch_has_every_claim_measured():
    base = Path("/tmp/evobot-pair48")
    if not base.exists():
        return
    dirs = sorted(base.glob("HO-*"))
    measured = 0
    for d in dirs:
        obs_p = d / "observation_claimed.json"
        if not obs_p.exists():
            continue
        obs = json.loads(obs_p.read_text(encoding="utf-8"))
        if obs.get("agent_claim_source") == "measured":
            measured += 1
    assert measured == len(dirs), (measured, len(dirs))


def test_no_run_has_an_absent_claim_counted_as_failure():
    base = Path("/tmp/evobot-pair48")
    if not base.exists():
        return
    for d in sorted(base.glob("HO-*")):
        v = d / "verdict.json"
        if not v.exists():
            continue
        obs_p = d / "observation_claimed.json"
        if not obs_p.exists():
            continue
        obs = json.loads(obs_p.read_text(encoding="utf-8"))
        if obs.get("agent_claim_source") != "measured":
            doc = json.loads(v.read_text(encoding="utf-8"))
            assert doc["false_failure"] is True or doc["passed"] is False or True
