#!/usr/bin/env python3
"""Same-bin destination spreading: physics, not answer leakage."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "baselines"))
import spread_destinations as sd

Z1 = [0.12, -0.15, 0.0175]
Z2 = [0.25, 0.05, 0.0175]


def test_two_stages_into_one_bin_become_distinct():
    stages = [{"object_name": "a", "place_pose": list(Z1)},
              {"object_name": "b", "place_pose": list(Z1)}]
    out = sd.spread(stages)
    assert out[0]["place_pose"] != out[1]["place_pose"]
    d = ((out[0]["place_pose"][0] - out[1]["place_pose"][0]) ** 2 +
         (out[0]["place_pose"][1] - out[1]["place_pose"][1]) ** 2) ** 0.5
    assert d >= 0.05, d


def test_both_destinations_stay_inside_the_bin_radius():
    import math
    stages = [{"object_name": "a", "place_pose": list(Z1)},
              {"object_name": "b", "place_pose": list(Z1)}]
    for s in sd.spread(stages):
        assert math.hypot(s["place_pose"][0] - Z1[0], s["place_pose"][1] - Z1[1]) <= 0.06


def test_single_object_plan_is_untouched():
    stages = [{"object_name": "a", "place_pose": list(Z1)}]
    assert sd.spread(stages)[0]["place_pose"] == Z1


def test_different_bins_are_not_treated_as_one_group():
    stages = [{"object_name": "a", "place_pose": list(Z1)},
              {"object_name": "b", "place_pose": list(Z2)}]
    out = sd.spread(stages)
    assert out[0]["place_pose"] == Z1 and out[1]["place_pose"] == Z2


def test_spread_is_deterministic_and_does_not_mutate_input():
    import json
    stages = [{"object_name": "a", "place_pose": list(Z1)},
              {"object_name": "b", "place_pose": list(Z1)}]
    before = json.dumps(stages, sort_keys=True)
    assert sd.spread(stages) == sd.spread(stages)
    assert json.dumps(stages, sort_keys=True) == before


def test_spacing_survives_measured_drift_above_clearance():
    """Regression for 4 real failures: spacing must exceed clearance + drift."""
    CLEARANCE = 0.05      # plan clearance contract
    DRIFT = 0.010         # observed landing drift on the robot
    assert sd.SPREAD_STEP_M > CLEARANCE + DRIFT, sd.SPREAD_STEP_M
    assert sd.SPREAD_STEP_M / 2.0 < 0.06, "offsets must stay inside the bin radius"


def test_two_object_offsets_stay_inside_the_bin_radius():
    import math
    stages = [{"object_name": "a", "place_pose": list(Z1)},
              {"object_name": "b", "place_pose": list(Z1)}]
    for s in sd.spread(stages):
        assert math.hypot(s["place_pose"][0] - Z1[0], s["place_pose"][1] - Z1[1]) <= 0.06


def test_three_objects_in_one_bin_are_refused_not_squeezed():
    """0.09 m separation cannot fit 3 objects in a 60 mm bin. Refuse, do not squeeze."""
    import pytest
    stages = [{"object_name": n, "place_pose": list(Z1)} for n in "abc"]
    with pytest.raises(ValueError) as exc:
        sd.spread(stages)
    assert "cannot place 3 objects" in str(exc.value)
