"""Regression guards for the PLACE release-aperture verdict (R5 19.2).

The defect: a release was judged against the COMMANDED open position (0.02 m)
while this gripper reaches 0.0104 m in free space. The aperture error at full
open is therefore 0.0096 m, nearly twice the 0.005 m tolerance, and the check
survived only while the controller happened to report reached_goal. One stalled
flag turned a release that physically happened into a false PLACE failure.

The scenarios below pin both directions of the fix: the measured reachable
aperture must be accepted, a release that did not open must still fail, and no
tolerance may be widened. Pure python: no ROS node, no simulator, no window.
"""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/flexcell/flexcell_skills"))

from flexcell_skills.common import gripper_outcome
from flexcell_skills.release_aperture import (
    DEFAULT_CLOSED_POSITION_M, DEFAULT_TOLERANCE_M, effective_open_reference_m,
    release_aperture_verdict)

COMMANDED = 0.02      # gripper_open_position on this robot
REACHABLE = 0.0104    # measured free-space reach, R5 19.2
CLOSED = -0.011       # prismatic joint lower bound (pick_server default)


def state(reached=False, stalled=False, position=None):
    """The open_state dict the place path builds via common.gripper_outcome()."""
    return gripper_outcome(NS(reached_goal=reached, stalled=stalled,
                              position=position, effort=None),
                           requested=COMMANDED)


def verdict(open_state, reference=0.0, requested=COMMANDED,
            closed=DEFAULT_CLOSED_POSITION_M, tolerance=DEFAULT_TOLERANCE_M):
    return release_aperture_verdict(open_state, requested,
                                    reference_m=reference, closed_m=closed,
                                    tolerance_m=tolerance)


def test_a_release_that_reaches_the_commanded_aperture_passes():
    doc = verdict(state(reached=True, position=0.0205))
    assert doc["ok"] is True
    assert doc["reason"] == "reached"
    assert doc["detail"].startswith("release aperture confirmed")
    assert "position=0.0205" in doc["detail"]


def test_the_measured_reachable_aperture_passes_with_a_calibrated_reference():
    """R5 19.2: 0.0104 m of a commanded 0.02 m is a normal full open here."""
    open_state = state(stalled=True, position=REACHABLE)
    # gripper_outcome still reports the pre-fix view; the verdict must not rely
    # on reached_goal to survive it.
    assert open_state["reached_goal"] is False
    assert open_state["stalled"] is True
    assert open_state["aperture_error"] > DEFAULT_TOLERANCE_M
    doc = verdict(open_state, reference=REACHABLE)
    assert doc["ok"] is True
    assert doc["calibrated"] is True
    assert doc["detail"].startswith("release aperture confirmed")
    assert "reference=0.0104" in doc["detail"] and "stalled=True" in doc["detail"]


def test_the_same_measurement_still_fails_against_the_commanded_reference():
    """The failure stays a failure; only its reason becomes accurate."""
    doc = verdict(state(stalled=True, position=REACHABLE), reference=COMMANDED)
    assert doc["ok"] is False
    assert doc["reason"] == "short_of_reference"
    # Downstream classifiers match this prefix (execution_root_cause.py,
    # evolution/proposals/generate.py), so it survives the fix.
    assert doc["detail"].startswith("gripper did not open")
    for fact in ("position=0.0104", "requested=0.02", "reference=0.02",
                 "stalled=True"):
        assert fact in doc["detail"]
    assert "0.0096 m from the reachable open reference" in doc["detail"]


def test_a_gripper_that_never_moved_fails_and_names_the_closed_position():
    doc = verdict(state(stalled=True, position=CLOSED), reference=REACHABLE)
    assert doc["ok"] is False
    assert doc["reason"] == "no_motion"
    assert doc["detail"].startswith("gripper did not open")
    assert "position=-0.011" in doc["detail"] and "requested=0.02" in doc["detail"]
    assert "reference=0.0104" in doc["detail"] and "stalled=True" in doc["detail"]
    assert "never left the closed position -0.011" in doc["detail"]


def test_a_non_finite_reading_is_refused_and_not_excused_by_reached_goal():
    for bad in (float("nan"), float("inf"), float("-inf")):
        doc = verdict(state(reached=True, position=bad), reference=REACHABLE)
        assert doc["ok"] is False
        assert doc["reason"] == "nonfinite"
        assert doc["detail"].startswith("gripper did not open")
        assert "requested=0.02" in doc["detail"]
        assert "stalled=False" in doc["detail"]
        assert "is not a finite number" in doc["detail"]


def test_a_state_without_the_released_flag_is_decided_by_the_measurement():
    """A caller may not carry reached_goal at all; that must not raise."""
    reached_by_measurement = state(stalled=True, position=REACHABLE)
    reached_by_measurement.pop("reached_goal")
    doc = verdict(reached_by_measurement, reference=REACHABLE)
    assert doc["ok"] is True and doc["reason"] == "reached"
    assert doc["reached_goal"] is False

    never_moved = state(stalled=True, position=CLOSED)
    never_moved.pop("reached_goal")
    doc = verdict(never_moved, reference=REACHABLE)
    assert doc["ok"] is False and doc["reason"] == "no_motion"


# ---------- guards that the fix did not become a relaxation ----------

def test_the_tolerance_is_the_same_five_millimetres():
    assert DEFAULT_TOLERANCE_M == 0.005
    assert verdict(state(position=REACHABLE + 0.0045),
                   reference=REACHABLE)["ok"] is True
    assert verdict(state(position=REACHABLE + 0.0055),
                   reference=REACHABLE)["ok"] is False


def test_a_release_that_barely_moved_off_the_closed_end_still_fails():
    doc = verdict(state(position=CLOSED + 0.001), reference=REACHABLE)
    assert doc["ok"] is False and doc["reason"] == "no_motion"


def test_reached_goal_cannot_rescue_a_measured_shortfall():
    doc = verdict(state(reached=True, position=REACHABLE), reference=COMMANDED)
    assert doc["ok"] is False and doc["detail"].startswith("gripper did not open")


def test_an_uncalibrated_reference_keeps_the_old_strict_comparison():
    """0.0 means "not calibrated": the command is used, nothing is loosened."""
    assert effective_open_reference_m(COMMANDED, 0.0) == COMMANDED
    assert effective_open_reference_m(COMMANDED, None) == COMMANDED
    assert effective_open_reference_m(COMMANDED, float("nan")) == COMMANDED
    assert effective_open_reference_m(COMMANDED, -0.01) == COMMANDED
    assert effective_open_reference_m(COMMANDED, REACHABLE) == REACHABLE
    doc = verdict(state(stalled=True, position=REACHABLE))
    assert doc["ok"] is False and doc["calibrated"] is False
    assert "gripper_open_reference_m is uncalibrated (0.0)" in doc["detail"]


def test_an_uncalibrated_reached_goal_stays_accepted_but_is_labelled():
    """Without a calibrated reference the pre-fix acceptance is kept on purpose.

    The command (0.02 m) is unreachable on this gripper, so the uncalibrated
    branch has nothing to measure against. Dropping its only acceptance path
    would fail the 103 recorded releases that measured 0.01027-0.01076 m
    instead of fixing one defect, so the branch keeps the old behaviour, says
    so in its detail, and disappears once the reference is calibrated.
    """
    doc = verdict(state(reached=True, position=REACHABLE))
    assert doc["ok"] is True
    assert doc["reason"] == "reached_goal_uncalibrated"
    assert doc["calibrated"] is False
    assert doc["detail"].startswith(
        "release aperture accepted without a calibrated reference")
    for fact in ("position=0.0104", "requested=0.02", "reference=0.02",
                 "stalled=False", "reached_goal=True"):
        assert fact in doc["detail"]
    # Calibrating the reference removes the branch and the measurement decides.
    calibrated = verdict(state(reached=True, position=REACHABLE), reference=REACHABLE)
    assert calibrated["reason"] == "reached"
    assert "uncalibrated" not in calibrated["detail"]


def test_an_unmeasured_aperture_is_not_a_failed_release():
    """The controller can be silent; that is not evidence the carry was not released."""
    doc = verdict(state(position=None), reference=REACHABLE)
    assert doc["ok"] is True and doc["reason"] == "unmeasured"
    assert "position=None" in doc["detail"]
    assert "drop check decides" in doc["detail"]


def test_invalid_limits_fail_closed():
    assert verdict(state(position=REACHABLE), reference=REACHABLE,
                   tolerance=float("nan"))["ok"] is False
    assert verdict(state(position=REACHABLE), reference=REACHABLE,
                   tolerance=-0.001)["ok"] is False


def test_place_server_wires_the_verdict_before_release():
    source = (ROOT / "src/flexcell/flexcell_skills/flexcell_skills/place_server.py").read_text()
    assert "from flexcell_skills.release_aperture import" in source
    assert "release_aperture_verdict(" in source
    assert "declare_parameter('gripper_open_reference_m'" in source
    assert "declare_parameter('gripper_closed_position_m'" in source
    # The release decision must be the verdict, not a bare tolerance compare.
    assert 'aperture_error"] > self._release_aperture_tolerance_m' not in source
    assert "not open_state[\"reached_goal\"]" not in source
    assert source.index("release_aperture_verdict(") < source.index("res.released = True")
