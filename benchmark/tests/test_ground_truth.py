#!/usr/bin/env python3
"""Tests for ground-truth capture support in the observation bridge.

Regression for a real defect: T02 was graded FAIL on a CORRECT run, because the
protected object never appears in a skill log (it was never touched) and the bridge
reported it as absent. "Not observed" then read as "not proven unchanged".
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "evaluators"))

import evaluate as ev
import generate as gen
import observe_from_run as bridge

REAL_RUN = (ROOT / "setup/acceptance/c13c_admission_20261110"
            / "legacy-constrained/run-2f1d13a5a98c")


def test_ground_truth_covers_an_untouched_object():
    gt = {"objects": {"target_box_a": [0.22, 0.0, 0.0175, 0.0],
                      "target_box_b": [0.20, -0.18, 0.0175, 0.0]}}
    obs = bridge.build_observation(REAL_RUN, ["target_box_a", "target_box_b"],
                                   ground_truth=gt)
    assert obs["_absent"] == []
    assert obs["_provenance"]["target_box_a"] == "gz.ground_truth"
    assert set(obs["_ground_truth_used"]) == {"target_box_a", "target_box_b"}


def test_without_ground_truth_the_untouched_object_is_absent():
    obs = bridge.build_observation(REAL_RUN, ["target_box_a", "target_box_b"])
    # box_a is never touched in this archived run either, so it is absent
    assert "target_box_a" in obs["_absent"] or "target_box_a" in obs["objects"]


def test_ground_truth_makes_an_exclusion_task_passable():
    spec = gen.generate("T02_exclusion", 1000)
    protected = spec["expected_goal"]["unmoved"][0]
    placed = [n for n in spec["expected_goal"]["placement"]]
    zone = spec["zones"][0]
    gt = {"objects": {}}
    for n in placed:
        gt["objects"][n] = [zone["pose"][0], zone["pose"][1], 0.0175, 0.0]
    for o in spec["objects"]:
        if o["name"] == protected:
            gt["objects"][o["name"]] = list(o["initial_pose"])
    obs = bridge.build_observation(REAL_RUN, [o["name"] for o in spec["objects"]],
                                   ground_truth=gt)
    clean = bridge.strip_diagnostics(obs)
    verdict = ev.evaluate(spec, clean)
    assert verdict["passed"] is True, verdict["failed_clauses"]


def test_ground_truth_cannot_overwrite_an_object_it_does_not_declare():
    gt = {"objects": {"target_box_z": [1.0, 1.0, 1.0, 0.0]}}
    obs = bridge.build_observation(REAL_RUN, ["target_box_a"], ground_truth=gt)
    assert "target_box_z" not in obs["objects"]


def test_strip_diagnostics_still_yields_the_contract_only():
    gt = {"objects": {"target_box_a": [0.22, 0.0, 0.0175, 0.0]}}
    obs = bridge.build_observation(REAL_RUN, ["target_box_a"], ground_truth=gt)
    clean = bridge.strip_diagnostics(obs)
    assert set(clean) == {"objects", "move_sequence", "agent_claimed_success", "visits"}

