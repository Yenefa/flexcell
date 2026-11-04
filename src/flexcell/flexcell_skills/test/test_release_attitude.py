"""Regression guards for the issue #121 pre-release attitude gate.

Pure-python checks only: quaternion geometry, fail-closed behaviour, the
provisional limit, and that the place server actually wired the gate in.
No simulator, ROS node, physical window or acceptance gate is added here.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src/flexcell/flexcell_skills"))

import release_drift_analysis as rda
from flexcell_skills.release_attitude import (
    DEFAULT_MAX_RELEASE_TILT_DEG, attitude_gate, tilt_deg, up_vector)


def quat_about_y(deg):
    half = math.radians(deg) / 2.0
    return (0.0, math.sin(half), 0.0, math.cos(half))


def quat_about_z(deg):
    half = math.radians(deg) / 2.0
    return (0.0, 0.0, math.sin(half), math.cos(half))


def test_identity_points_up_and_passes():
    q = (0.0, 0.0, 0.0, 1.0)
    assert up_vector(q) == (0.0, 0.0, 1.0)
    assert tilt_deg(q) == 0.0
    ok, detail = attitude_gate(q)
    assert ok and "within" in detail


def test_yaw_does_not_count_as_tilt():
    assert tilt_deg(quat_about_z(90)) < 1e-9
    assert attitude_gate(quat_about_z(90))[0] is True


def test_issue_121_c_quaternion_is_refused():
    q = (0.094056, 0.434123, 0.472795, 0.761023)
    assert abs(tilt_deg(q) - 52.744) < 0.01
    ok, detail = attitude_gate(q)
    assert ok is False
    assert "carry held" in detail and "52.7" in detail


def test_issue_121_b_tilt_is_refused():
    ok, detail = attitude_gate(quat_about_y(26.13))
    assert ok is False and "carry held" in detail


def test_normal_historical_attitudes_are_admitted():
    for deg in (0.22, 2.04, 4.89, 7.70, 15.18):
        assert attitude_gate(quat_about_y(deg))[0] is True


def test_limit_is_inclusive_and_one_sided():
    assert attitude_gate(quat_about_y(DEFAULT_MAX_RELEASE_TILT_DEG))[0] is True
    assert attitude_gate(quat_about_y(DEFAULT_MAX_RELEASE_TILT_DEG + 0.01))[0] is False
    assert attitude_gate(quat_about_y(-7.0))[0] is True


def test_bad_or_unavailable_quaternion_is_refused_not_guessed():
    for q in (None, (), (0, 0, 0), (0, 0, 0, 0),
              (float("nan"), 0, 0, 1), (0, 0, 0, float("inf"))):
        ok, detail = attitude_gate(q)
        assert ok is False and "unavailable" in detail


def test_invalid_limit_is_refused():
    assert attitude_gate((0, 0, 0, 1), max_deg=-1.0)[0] is False
    assert attitude_gate((0, 0, 0, 1), max_deg=float("nan"))[0] is False


def test_gate_geometry_agrees_with_the_offline_analysis_module():
    for deg in (0.0, 7.0, 15.0, 26.13, 52.74):
        q = quat_about_y(deg)
        assert abs(tilt_deg(q) - rda.tilt_deg(q)) < 1e-9
    assert abs(tilt_deg((0.094056, 0.434123, 0.472795, 0.761023))
               - rda.tilt_deg((0.094056, 0.434123, 0.472795, 0.761023))) < 1e-9


def test_place_server_wires_the_gate_before_release():
    source = (ROOT / "src/flexcell/flexcell_skills/flexcell_skills/place_server.py").read_text()
    assert "from flexcell_skills.release_attitude import (" in source
    assert "attitude_gate(" in source
    assert "release_tilt_deg" in source
    assert "max_release_tilt_deg" in source
    # The gate must run before the carry release service is called.
    assert source.index("attitude_ok, attitude_detail") < source.index("res.released = True")
