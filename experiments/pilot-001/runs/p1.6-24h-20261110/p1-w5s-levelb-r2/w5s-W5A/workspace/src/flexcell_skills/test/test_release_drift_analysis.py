"""Regression guards for the read-only issue #121 release-drift analysis.

Only the new geometry/direction logic is tested. No simulator, ROS node,
physical window or acceptance gate is added here.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

import release_drift_analysis as rda


def test_identity_quaternion_points_up_and_has_zero_tilt():
    assert rda.up_vector((0.0, 0.0, 0.0, 1.0)) == (0.0, 0.0, 1.0)
    assert rda.tilt_deg((0.0, 0.0, 0.0, 1.0)) == 0.0


def test_yaw_about_world_z_does_not_tilt_the_box():
    q = (0.0, 0.0, math.sin(math.radians(30)), math.cos(math.radians(30)))
    assert rda.tilt_deg(q) < 1e-9
    assert rda.geometric_shift_mm(rda.tilt_deg(q)) == 0.0


def test_issue_121_quaternion_reproduces_the_reported_tilt():
    q = (0.094056, 0.434123, 0.472795, 0.761023)
    assert abs(rda.tilt_deg(q) - 52.74) < 0.05


def test_geometric_shift_is_zero_at_rest_and_monotonic_before_45_degrees():
    assert rda.geometric_shift_mm(0.0) == 0.0
    values = [rda.geometric_shift_mm(t) for t in (0, 5, 10, 15, 26, 32, 44)]
    assert all(b > a for a, b in zip(values, values[1:]))
    assert abs(values[3] - 5.126) < 0.05


def test_tipping_regime_splits_at_45_degrees():
    assert rda.tipping_regime(26.13) == "ROCK_BACK"
    assert rda.tipping_regime(52.74) == "ROLL_OVER_BEYOND_LOCAL_SAMPLE_RANGE"


def test_direction_cosine_is_minus_one_for_a_pure_tip_over():
    # Box tilted so its up-vector leans towards +x; it must fall towards -x.
    theta = math.radians(15)
    q = (0.0, math.sin(theta / 2), 0.0, math.cos(theta / 2))
    before = [0.0, 0.0, 0.030, *q]
    after = [-0.005, 0.0, 0.0175]
    assert rda.direction_cosine(q, before, after) == -1.0


def test_direction_cosine_is_none_when_there_is_no_horizontal_signal():
    q = (0.0, 0.0, 0.0, 1.0)
    before = [0.0, 0.0, 0.030, *q]
    assert rda.direction_cosine(q, before, before) is None


def test_analyze_record_extracts_the_fields_the_current_gate_ignores():
    q = (0.0, 0.130526, 0.0, 0.991445)  # 15 deg about y
    rec = {
        "object_before_release": [0.12, -0.15, 0.0302, *q],
        "box_after": [0.115, -0.15, 0.0175],
        "place_error_m": 0.005,
        "skill_backend": "mtc",
    }
    row = rda.analyze_record(rec, "unit-test")
    assert row is not None
    assert abs(row["tilt_deg"] - 15.0) < 0.05
    assert abs(row["shift_mm"] - 5.0) < 0.01
    assert row["direction_cosine"] == -1.0
    assert row["regime"] == "ROCK_BACK"


def test_incomplete_records_are_not_guessed():
    assert rda.analyze_record({"object_before_release": [0, 0, 0],
                               "box_after": [0, 0, 0]}, "x") is None
    assert rda.analyze_record({}, "x") is None


def test_gate_simulation_counts_admitted_and_refused_without_claiming_success():
    rows = [
        {"tilt_deg": 5.0, "place_error_mm": 2.0},
        {"tilt_deg": 26.0, "place_error_mm": 10.5},
        {"tilt_deg": 52.0, "place_error_mm": 27.0},
    ]
    out = rda.gate_simulation(rows, limits=(10, 20))
    assert out[0]["admitted"] == 1 and out[0]["refused"] == 2
    assert out[0]["admitted_over_10mm"] == 0
    assert out[1]["admitted"] == 1 and out[1]["refused"] == 2
    assert out[1]["max_settled_error_mm"] == 2.0


def test_noise_level_shifts_are_excluded_from_the_direction_statistic():
    q = (0.0, 0.0, 0.0, 1.0)
    rec = {"object_before_release": [0.0, 0.0, 0.030, *q],
           "box_after": [0.00000001, 0.0, 0.0175],
           "place_error_m": 0.00000001}
    row = rda.analyze_record(rec, "noise")
    assert row["shift_mm"] < rda.MIN_SHIFT_MM
    report = rda.summarize(["noise"], [row])
    assert report["records_usable_for_direction"] == 0
    assert report["noise_level_records_excluded"] == 1
    assert report["direction_cosine_mean"] is None


def test_issue_121_reference_point_recomputes_without_the_cloud_logs():
    result = rda.issue121_check()
    c = result["layout2_C"]
    assert abs(c["quaternion_recomputed_tilt_deg"] - c["issue_reported_tilt_deg"]) < 0.05
    assert abs(c["recomputed_settled_error_mm"] - c["issue_reported_settled_error_mm"]) < 0.01
    assert c["direction_cosine"] < -0.99
    assert abs(c["pre_release_position_error_mm"] - 0.221) < 0.01
    assert c["regime"] == "ROLL_OVER_BEYOND_LOCAL_SAMPLE_RANGE"
    assert abs(c["release_clearance_above_target_mm"] - 12.697) < 0.01
