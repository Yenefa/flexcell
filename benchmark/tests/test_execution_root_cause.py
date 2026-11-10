#!/usr/bin/env python3
"""Tests for execution root-cause classification from EPISODE records."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "erc", ROOT / "runtime" / "recovery" / "execution_root_cause.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def test_release_stall_is_identified():
    assert E.classify(
        "gripper did not open (position=-0.011, requested=0.02, stalled=True)"
    ) == "ACTUATOR_STALL_ON_RELEASE"


def test_grasp_stall_is_identified():
    assert E.classify("gripper did not close (position=0.03)") == "ACTUATOR_STALL_ON_GRASP"


def test_kinematics_is_separated_from_actuation():
    assert E.classify("ik unreachable for target") == "KINEMATICS"


def test_unrelated_detail_is_not_forced_into_a_class():
    assert E.classify("task done") == "OTHER"
    assert E.classify("") == "OTHER"
    assert E.classify(None) == "OTHER"


def test_episode_failures_reads_executor_results(tmp_path):
    ep = tmp_path / "ep.json"
    ep.write_text(json.dumps({"steps": [
        {"executor_result": {"outcome": 0, "detail": "picked"}},
        {"executor_result": {"outcome": 1,
                             "detail": "gripper did not open (position=-0.011)"}},
    ]}), encoding="utf-8")
    got = E.episode_failures(str(ep))
    assert len(got) == 1
    assert "did not open" in got[0]["detail"]


def test_missing_episode_returns_nothing_instead_of_raising(tmp_path):
    assert E.episode_failures(str(tmp_path / "nope.json")) == []

