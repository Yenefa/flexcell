#!/usr/bin/env python3
"""Tests for the ANOMALY / INVALID split in the batch validator.

WHY THE SPLIT EXISTS: the first version treated every surprise as "BATCH INVALID". When a
retry was issued although the first attempt had already PASSED, that made the whole batch
unreportable - which is wrong. The verdicts and the claims are sound; what is surprising is
that the SKILL LAYER reported a failure the measured world contradicts. Throwing the batch
away would hide a real finding about the skill layer, and calling it clean would hide it from
a reader. So the validator now separates:
  INVALID - a required step did not run  -> no number may be reported
  ANOMALY - data sound, surprising fact -> report it alongside the numbers
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
    for name, files in runs.items():
        d = tmp_path / name
        d.mkdir()
        for fname, content in files.items():
            (d / fname).write_text(json.dumps(content), encoding="utf-8")
    rc = subprocess.run([sys.executable, str(ROOT / "experiments" / "baselines"
                                             / "validate_batch.py"), str(tmp_path)],
                        capture_output=True, text=True)
    return rc.returncode, rc.stdout


def _ok():
    return {"verdict_after1.json": {"passed": True}, "verdict.json": {"passed": True},
            "observation_claimed.json": {"agent_claim_source": "measured"},
            "recovery_decision.json": {"action": "no_recovery"}}


def test_a_retry_after_a_passing_first_attempt_is_an_anomaly_not_a_failure(tmp_path):
    runs = {"HO-a": dict(_ok(), **{"plan_retry.json": {"stages": []}})}
    rc, out = _run(tmp_path, runs)
    assert rc == 0, out                      # the batch is still usable
    assert "SKILL_LAYER_DISAGREEMENT" in out  # but the disagreement is visible
    assert "recovery_decision.json" in json.dumps(runs)  # fixture sanity


def test_recovery_ran_is_counted_even_when_nothing_failed(tmp_path):
    """The earlier counter only ticked recovery on failure, so it reported 0 for a batch
    where the driver had in fact run on every instance."""
    runs = {"HO-a": _ok(), "HO-b": _ok()}
    rc, out = _run(tmp_path, runs)
    assert rc == 0
    assert '"recovery_ran": 2' in out, out


def test_a_batch_with_no_failures_cannot_support_a_recovery_claim(tmp_path):
    runs = {"HO-a": _ok()}
    rc, out = _run(tmp_path, runs)
    assert rc == 0
    assert "no claim about recovery EFFICACY" in out


def test_a_failed_attempt_without_recovery_is_still_invalid(tmp_path):
    runs = {"HO-a": dict(_ok(), **{"verdict_after1.json": {"passed": False}}),
            "HO-b": dict(_ok(), **{"verdict_after1.json": {"passed": False},
                                   "recovery_decision.json": {"action": "resume"},
                                   "plan_retry.json": {"stages": []}})}
    # remove HO-a's decision to reproduce the pair48 shape
    del runs["HO-a"]["recovery_decision.json"]
    rc, out = _run(tmp_path, runs)
    assert rc == 1
    assert "recovery never ran" in out


def test_failures_with_zero_retries_is_invalid(tmp_path):
    runs = {"HO-a": dict(_ok(), **{"verdict_after1.json": {"passed": False}})}
    rc, out = _run(tmp_path, runs)
    assert rc == 1
    assert "not a recovery arm" in out
