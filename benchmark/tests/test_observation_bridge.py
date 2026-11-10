#!/usr/bin/env python3
"""Tests for the run -> observation bridge, using a REAL archived run.

The fixture is a real Gazebo run from this repository (c13c, legacy arm), not a
hand-written stub, because the whole point of the bridge is to read the shape the
runtime actually writes.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "evaluators"))

import evaluate as ev
import observe_from_run as bridge
import generate as gen

REAL_RUN = (ROOT / "setup/acceptance/c13c_admission_20261110"
            / "legacy-constrained/run-2f1d13a5a98c")


def test_bridge_reads_a_real_run_without_crashing():
    assert (REAL_RUN / "skills").is_dir(), "fixture run missing"
    obs = bridge.build_observation(REAL_RUN, ["target_box_a", "target_box_b"])
    assert isinstance(obs["objects"], dict)
    assert obs["_run_dir"].endswith("run-2f1d13a5a98c")


def test_bridge_prefers_verify_over_place_for_the_same_object():
    obs = bridge.build_observation(REAL_RUN, ["target_box_b"])
    assert "target_box_b" in obs["objects"]
    assert obs["_provenance"]["target_box_b"] == "verify.measured"
    # the archived verify record measured the box at its placed position
    x, y, z, _ = obs["objects"]["target_box_b"]
    assert abs(x - 0.2532) < 1e-3 and abs(y - 0.0509) < 1e-3


def test_unmeasured_object_is_absent_not_assumed_unchanged():
    obs = bridge.build_observation(REAL_RUN, ["target_box_a", "target_box_b", "target_box_c"])
    assert "target_box_c" in obs["_absent"]
    assert "target_box_c" not in obs["objects"]


def test_absent_object_makes_a_real_task_fail():
    spec = gen.generate("T02_exclusion", 5)
    names = [o["name"] for o in spec["objects"]]
    obs = bridge.build_observation(REAL_RUN, names)
    verdict = ev.evaluate(spec, bridge.strip_diagnostics(obs))
    assert verdict["passed"] is False
    assert verdict["failed_clauses"], "a run that did not do the task must fail"


def test_bridge_does_not_read_the_spec_so_it_cannot_bias_the_observation():
    # Same run, two different declared object sets: the measured poses must agree
    a = bridge.build_observation(REAL_RUN, ["target_box_b"])
    b = bridge.build_observation(REAL_RUN, ["target_box_b", "target_box_a"])
    assert a["objects"]["target_box_b"] == b["objects"]["target_box_b"]


def test_strip_diagnostics_leaves_exactly_the_evaluator_contract():
    obs = bridge.build_observation(REAL_RUN, ["target_box_b"])
    clean = bridge.strip_diagnostics(obs)
    # The contract grew by "visits" when relay grading was added: a template that asks
    # for an intermediate stop cannot be graded from final positions alone.
    assert set(clean) == {"objects", "move_sequence", "agent_claimed_success", "visits"}
    # and the evaluator accepts it
    spec = gen.generate("T01_multi_object_sorting", 3)
    verdict = ev.evaluate(spec, clean)
    assert "passed" in verdict


def test_missing_skills_directory_yields_an_empty_observation():
    obs = bridge.build_observation(ROOT / "benchmark", ["target_box_a"])
    assert obs["objects"] == {}
    assert obs["_absent"] == ["target_box_a"]
