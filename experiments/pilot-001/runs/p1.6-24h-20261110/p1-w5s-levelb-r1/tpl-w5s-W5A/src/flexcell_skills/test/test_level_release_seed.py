"""Offline counter-examples for the issue #121 level-release IK seed.

These joint vectors were produced by scripts/level_release_seed.py against the
real upstream URDF and are frozen here as regression fixtures. They prove the
null space is usable: two different pitches hit the SAME box-centre target
with zero position error, both inside joint limits, with identical yaw.

Pure-python only: no scipy, no ROS, no simulator.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

import fourdof_reachability as fk
import level_release_seed as seed
import release_drift_analysis as rda

CHAIN = [
    ((0.012, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ((0.0, 0.0, 0.0595), (0.0, 1.0, 0.0)),
    ((0.024, 0.0, 0.128), (0.0, 1.0, 0.0)),
    ((0.124, 0.0, 0.0), (0.0, 1.0, 0.0)),
]
EE = (0.126, 0.0, 0.0)
OFFSET = seed.DEFAULT_BOX_OFFSET

# run104 descend box target, solver outputs at phi=0 and phi=6.7 deg.
TARGET_A = (0.12, -0.15, 0.0295)
LEVEL_A = (-0.891507, -0.773305, 0.620058, 0.153247)
TILTED_A = (-0.891507, -0.598920, 0.415418, 0.300439)

# issue #121 staging box target, solver outputs at phi=0 and phi=26.13 deg.
TARGET_B = (0.12, 0.04, 0.0295)
LEVEL_B = (0.443474, -1.335942, 0.694827, 0.641114)
TILTED_B = (0.443474, -0.579171, 0.163481, 0.871744)


def assert_hits(q, target):
    p = seed.attached_point_position(q, CHAIN, EE, OFFSET)
    assert math.dist(p, target) < 1e-5
    assert fk.joint_limits_ok(q)


def test_both_pitches_hit_the_same_recorded_box_target():
    assert_hits(LEVEL_A, TARGET_A)
    assert_hits(TILTED_A, TARGET_A)
    assert LEVEL_A[0] == TILTED_A[0]  # yaw unchanged: pure null-space move
    assert abs(fk.pitch_deg(LEVEL_A)) < 1e-4
    assert abs(fk.pitch_deg(TILTED_A) - 6.7) < 1e-3


def test_level_seed_is_actually_level():
    up = fk.ee_up(LEVEL_A, CHAIN, EE)
    assert abs(up[2] - 1.0) < 1e-9
    assert math.degrees(math.acos(max(-1, min(1, up[2])))) < 1e-6
    assert rda.geometric_shift_mm(0.0) == 0.0


def test_tilted_seed_predicts_the_recorded_drift():
    up = fk.ee_up(TILTED_A, CHAIN, EE)
    tilt = math.degrees(math.acos(max(-1, min(1, up[2]))))
    assert abs(tilt - 6.7) < 1e-3
    assert abs(rda.geometric_shift_mm(tilt) - 2.1613) < 0.01


def test_issue_121_staging_point_has_the_same_null_space():
    assert_hits(LEVEL_B, TARGET_B)
    assert_hits(TILTED_B, TARGET_B)
    assert LEVEL_B[0] == TILTED_B[0]
    tilt = math.degrees(math.acos(max(-1, min(1, fk.ee_up(TILTED_B, CHAIN, EE)[2]))))
    assert abs(tilt - 26.13) < 1e-3
    predicted = rda.geometric_shift_mm(tilt)
    assert abs(predicted - 9.4957) < 0.01
    # Issue #121 measured 10.533 mm; the gap must stay inside the model RMSE.
    assert abs(predicted - 10.533) < 1.12


def test_offset_is_applied_in_the_ee_frame_not_the_world_frame():
    # With a non-zero pitch, a world-frame offset would give a different point.
    ee = fk.ee_position(TILTED_B, CHAIN, EE)
    world_offset = tuple(TARGET_B[i] - ee[i] for i in range(3))
    assert any(abs(world_offset[i] - OFFSET[i]) > 0.01 for i in range(3))


def test_seed_does_not_move_the_box_target():
    for q, target in ((LEVEL_A, TARGET_A), (TILTED_A, TARGET_A),
                      (LEVEL_B, TARGET_B), (TILTED_B, TARGET_B)):
        p = seed.attached_point_position(q, CHAIN, EE, OFFSET)
        assert all(abs(p[i] - target[i]) < 1e-5 for i in range(3))
