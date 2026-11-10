#!/usr/bin/env python3
"""Tests for the batch reporter: refuse unvalidated batches, report pairs and intervals.

WHY: the reporter is the last place a wrong number could reach a report. Two earlier
batches produced plausible-looking metrics while a pipeline step had silently not run, so
the reporter must gate on structural validation FIRST and must report the paired difference
rather than two independent rates that would hide the correlation between arms.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "rb", ROOT / "experiments" / "baselines" / "report_batch.py")
RB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RB)


def _mk(tmp_path, runs):
    for name, files in runs.items():
        d = tmp_path / name
        d.mkdir()
        for fname, content in files.items():
            (d / fname).write_text(json.dumps(content), encoding="utf-8")
    return tmp_path


def _report(tmp_path):
    return subprocess.run(
        [sys.executable, str(ROOT / "experiments" / "baselines" / "report_batch.py"),
         str(tmp_path)], capture_output=True, text=True)


def test_wilson_interval_is_not_a_point(tmp_path):
    p, lo, hi = RB.wilson(14, 16)
    assert 0.85 < p < 0.89
    assert lo < p < hi
    assert hi - lo > 0.2, "a 16-instance rate must carry a wide interval"


def test_an_invalid_batch_produces_no_metrics(tmp_path):
    """This is the pair48 shape: a failed first attempt with no recovery decision."""
    runs = {"HO-a": {"verdict_after1.json": {"passed": False},
                     "verdict.json": {"passed": False},
                     "observation_claimed.json": {"agent_claim_source": "measured"}}}
    d = _mk(tmp_path, runs)
    out = _report(d)
    assert out.returncode != 0
    assert "REFUSING to report metrics" in out.stdout


def test_a_valid_batch_reports_paired_gain(tmp_path):
    base = {"observation_claimed.json": {"agent_claim_source": "measured"}}
    runs = {
        "HO-a": dict(base, **{"verdict_after1.json": {"passed": True},
                              "verdict.json": {"passed": True,
                                               "agent_claimed_success": True}}),
        "HO-b": dict(base, **{"verdict_after1.json": {"passed": False},
                              "verdict.json": {"passed": True,
                                               "agent_claimed_success": True},
                              "recovery_decision.json": {"action": "resume"},
                              "plan_retry.json": {"stages": []}}),
        "HO-c": dict(base, **{"verdict_after1.json": {"passed": True},
                              "verdict.json": {"passed": True,
                                               "agent_claimed_success": True}}),
    }
    d = _mk(tmp_path, runs)
    out = _report(d)
    assert out.returncode == 0, out.stdout
    assert "gained 1" in out.stdout
    assert "lost 0" in out.stdout


def test_gain_is_attributed_only_to_retried_runs(tmp_path):
    """A pass that no retry touched must not be counted as a recovery gain."""
    base = {"observation_claimed.json": {"agent_claim_source": "measured"}}
    runs = {"HO-a": dict(base, **{"verdict_after1.json": {"passed": False},
                                  "verdict.json": {"passed": False,
                                                   "agent_claimed_success": False},
                                  "recovery_decision.json": {"action": "escalate"},
                                  "plan_retry.json": {"stages": []}})}
    d = _mk(tmp_path, runs)
    out = _report(d)
    assert "gained 0" in out.stdout
