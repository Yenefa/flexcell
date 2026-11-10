#!/usr/bin/env python3
"""Tests for the batch validator: a batch must prove its steps RAN before its numbers count.

THE FAILURE THESE GUARD: the pair48 batch reported "R 13/16" and looked like a normal
recovery arm. Recovery had never executed - the runner was still in the simulator checkout
and invoked recovery_driver.py by relative path, so every run logged "No such file or
directory". Arm R was byte-identical to arm B on all 16 runs. The same cwd trap had already
silently disabled the self-assessment.

A batch can be internally consistent and still measure nothing, so the validator checks for
evidence that each step ran rather than for plausible-looking values.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "vb", ROOT / "experiments" / "baselines" / "validate_batch.py")
VB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VB)


def _run(tmp_path, runs):
    """runs: list of dicts describing each fake run directory."""
    for name, files in runs.items():
        d = tmp_path / name
        d.mkdir()
        for fname, content in files.items():
            (d / fname).write_text(json.dumps(content), encoding="utf-8")
    rc = subprocess.run([sys.executable, str(ROOT / "experiments" / "baselines"
                                             / "validate_batch.py"), str(tmp_path)],
                        capture_output=True, text=True)
    return rc.returncode, rc.stdout


def _passing():
    return {"verdict_after1.json": {"passed": True}, "verdict.json": {"passed": True},
            "observation_claimed.json": {"agent_claim_source": "measured"}}


def test_a_healthy_batch_validates(tmp_path):
    runs = {"HO-a": _passing(),
            "HO-b": dict(_passing(),
                         **{"verdict_after1.json": {"passed": False},
                            "recovery_decision.json": {"action": "resume"},
                            "plan_retry.json": {"stages": []}})}
    rc, out = _run(tmp_path, runs)
    assert rc == 0, out


def test_failed_first_attempt_without_a_recovery_decision_invalidates(tmp_path):
    """This is exactly what happened: nothing recorded, nothing ran."""
    runs = {"HO-a": dict(_passing(), **{"verdict_after1.json": {"passed": False}})}
    rc, out = _run(tmp_path, runs)
    assert rc == 1
    assert "recovery never ran" in out


def test_a_batch_with_no_retries_at_all_is_flagged(tmp_path):
    runs = {"HO-a": dict(_passing(), **{"verdict_after1.json": {"passed": False},
                                        "recovery_decision.json": {"action": "resume"}})}
    rc, out = _run(tmp_path, runs)
    assert rc == 1
    assert "arm R is not a recovery arm" in out


def test_a_run_without_a_measured_claim_is_flagged(tmp_path):
    runs = {"HO-a": {"verdict_after1.json": {"passed": True},
                     "verdict.json": {"passed": True}}}
    rc, out = _run(tmp_path, runs)
    assert rc == 1
    assert "unmeasurable" in out


def test_a_claim_present_but_not_marked_measured_is_flagged(tmp_path):
    runs = {"HO-a": dict(_passing(),
                         **{"observation_claimed.json": {"agent_claim_source": "absent"}})}
    rc, out = _run(tmp_path, runs)
    assert rc == 1
    assert "not marked measured" in out
