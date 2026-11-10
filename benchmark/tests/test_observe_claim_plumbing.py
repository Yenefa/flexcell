#!/usr/bin/env python3
"""Tests for the claim plumbing in the observation bridge.

The defect: build_observation defaulted agent_claimed_success to False, so a missing claim
was byte-identical to a measured claim of failure. That is what made false_success a
structural zero. The fix exposes a missing claim as None and records where it came from,
and the CLI now has a way to supply one at all - previously there was none.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ofr", ROOT / "benchmark" / "evaluators" / "observe_from_run.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def _empty_run(tmp_path):
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_a_missing_claim_is_exposed_as_unknown_not_false(tmp_path):
    run = _empty_run(tmp_path)
    obs = M.build_observation(run, ["a"])
    assert obs["agent_claimed_success"] is None
    assert obs["agent_claim_source"] == "absent"


def test_a_supplied_claim_is_kept_and_marked_measured(tmp_path):
    run = _empty_run(tmp_path)
    for value in (True, False):
        obs = M.build_observation(run, ["a"], agent_claimed_success=value)
        assert obs["agent_claimed_success"] is value
        assert obs["agent_claim_source"] == "measured"


def test_the_cli_can_supply_a_claim(tmp_path):
    """There was literally no flag for this, which is why no batch ever recorded one."""
    run = _empty_run(tmp_path)
    out = tmp_path / "obs.json"
    rc = M.main([str(run), str(out), "a", "--agent-claim", "true"])
    assert rc == 0
    obs = json.loads(out.read_text(encoding="utf-8"))
    assert obs["agent_claimed_success"] is True
    assert obs["agent_claim_source"] == "measured"


def test_the_cli_defaults_to_unknown(tmp_path):
    run = _empty_run(tmp_path)
    out = tmp_path / "obs.json"
    M.main([str(run), str(out), "a"])
    obs = json.loads(out.read_text(encoding="utf-8"))
    assert obs["agent_claimed_success"] is None
    assert obs["agent_claim_source"] == "absent"


def test_claim_values_parse_leniently(tmp_path):
    run = _empty_run(tmp_path)
    for raw, want in (("true", True), ("success", True), ("1", True),
                      ("false", False), ("no", False)):
        out = tmp_path / ("obs_%s.json" % raw)
        M.main([str(run), str(out), "a", "--agent-claim", raw])
        assert json.loads(out.read_text(encoding="utf-8"))[
            "agent_claimed_success"] is want, raw
