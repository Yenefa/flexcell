"""Offline guards for the M2.3 audit P0 fixes (pure python: no rclpy, no ROS).

Covers:
- P0-1  trajectory_summary never raises on empty/malformed planner
        trajectories (the IndexError-escapes-_execute ghost-success class)
- P0-2  policy ABORT decisions map to typed task error codes
        (BUDGET_EXHAUSTED class -> ERR_RECOVERY_EXHAUSTED, not the
        PolicyStateError catch-all)
- P0-3  canceled vocabulary: canonicalize/status map the new OUTCOME_CANCELED
        constants for OBSERVE (2) and VERIFY (3)
"""

from flexcell_skills.contracts import error_codes as EC
from flexcell_skills.contracts.error_codes import (
    ERR_CANCELED, STATUS_CANCELED, canonicalize, status_from_outcome,
    task_abort_error_code)
from flexcell_skills.contracts.trajectory import trajectory_summary
from flexcell_skills.decision_policy import (
    RC_BUDGET_EXHAUSTED, RC_NON_RECOVERABLE, RC_OBSERVE_FAILED,
    RC_VERIFY_BUDGET_EXHAUSTED)


# ---------------------------------------------------------------- fakes
class _Time:
    def __init__(self, sec, nanosec):
        self.sec = sec
        self.nanosec = nanosec


class _Point:
    def __init__(self, sec, nanosec, positions):
        self.time_from_start = _Time(sec, nanosec)
        self.positions = positions


class _Traj:
    def __init__(self, points):
        self.joint_trajectory = type('JT', (), {'points': points})()


class _BrokenTraj:
    class joint_trajectory:   # noqa: N801 - duck-type sabotage
        points = None         # list() raises TypeError


class _UnreadablePoint:
    def __init__(self, sec, nanosec):
        self.time_from_start = _Time(sec, nanosec)
        # no .positions attribute


# ---------------------------------------------------------------- P0-1
def test_summary_empty_points():
    assert trajectory_summary(_Traj([])) == (0, None, None)


def test_summary_normal():
    npts, final, dur = trajectory_summary(
        _Traj([_Point(0, 500000000, [0.1, 0.2]),
               _Point(2, 0, [0.3, 0.4])]))
    assert npts == 2
    assert final == [0.3, 0.4]
    assert abs(dur - 2.0) < 1e-9


def test_summary_malformed_object():
    assert trajectory_summary(_BrokenTraj()) == (0, None, None)


def test_summary_unreadable_positions():
    npts, final, dur = trajectory_summary(_Traj([_UnreadablePoint(1, 0)]))
    assert npts == 1
    assert final is None


def test_summary_never_raises_on_any_of_the_audit_cases():
    # the audit's injection list: empty trajectory + arbitrary points[-1]
    # failure modes must ALL come back as typed (npts, None/positions, dur)
    for traj in (_Traj([]), _BrokenTraj(), _Traj([_UnreadablePoint(0, 0)]),
                 _Traj([_Point(0, 0, [0.0])])):
        out = trajectory_summary(traj)
        assert isinstance(out[0], int)


# ---------------------------------------------------------------- P0-2
def test_rc_reason_code_literals_are_frozen():
    # error_codes.py maps ABORT reasons by string; these cross-checks keep
    # the two modules honest if anyone renames a reason code
    assert RC_BUDGET_EXHAUSTED == 'BUDGET_EXHAUSTED'
    assert RC_VERIFY_BUDGET_EXHAUSTED == 'VERIFY_BUDGET_EXHAUSTED'
    assert RC_NON_RECOVERABLE == 'NON_RECOVERABLE'
    assert RC_OBSERVE_FAILED == 'OBSERVE_FAILED'


def test_abort_budget_exhausted_is_typed():
    assert task_abort_error_code(RC_BUDGET_EXHAUSTED) == EC.TASK_ERR_RECOVERY_EXHAUSTED
    assert task_abort_error_code(RC_VERIFY_BUDGET_EXHAUSTED) == EC.TASK_ERR_RECOVERY_EXHAUSTED
    assert EC.TASK_ERR_RECOVERY_EXHAUSTED == 51


def test_abort_non_budget_fails_closed_to_skill_failed():
    assert task_abort_error_code(RC_NON_RECOVERABLE) == EC.TASK_ERR_SKILL_FAILED
    assert task_abort_error_code(RC_OBSERVE_FAILED) == EC.TASK_ERR_SKILL_FAILED
    assert task_abort_error_code('SOMETHING_NEW') == EC.TASK_ERR_SKILL_FAILED
    assert EC.TASK_ERR_SKILL_FAILED == 50


# ---------------------------------------------------------------- P0-3
def test_canonicalize_canceled_observe():
    canonical, warning = canonicalize('OBSERVE', 32, 2)
    assert canonical == ERR_CANCELED
    assert warning is None


def test_canonicalize_canceled_verify():
    canonical, warning = canonicalize('VERIFY', 32, 3)
    assert canonical == ERR_CANCELED
    assert warning is None


def test_canonicalize_canceled_pick_and_place():
    for skill in ('PICK', 'PLACE'):
        canonical, warning = canonicalize(skill, 32, 2)
        assert canonical == ERR_CANCELED
        assert warning is None


def test_status_verify_canceled():
    assert status_from_outcome('VERIFY', 3) == STATUS_CANCELED
    # legacy canceled path for the motion skills is unchanged
    assert status_from_outcome('PICK', 2) == STATUS_CANCELED
    assert status_from_outcome('OBSERVE', 2) == STATUS_CANCELED


def test_status_verify_mismatch_still_failure():
    # the canceled addition must not disturb the honest MISMATCH=FAILURE rule
    assert status_from_outcome('VERIFY', 1) == EC.STATUS_FAILURE
    assert status_from_outcome('VERIFY', 2) == EC.STATUS_FAILURE
