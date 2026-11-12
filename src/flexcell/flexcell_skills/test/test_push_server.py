"""push_server node behaviour: result mapping, cancellation, typed refusals.

WHY A NODE-LEVEL TEST ON TOP OF THE PURE CONTRACT
    contracts/push.py already decides everything. What can still go wrong is the
    ADAPTER: a measured push turned into ERR_INTERNAL because a list was assigned
    to a Pose field, a NaN written into the JSONL log (invalid JSON, unreadable
    evidence), a cancel that reports the wrong outcome, or a crash that rclpy
    surfaces as a default Result with outcome=0 (which reads as SUCCEEDED).

    This file drives the REAL PushServer._execute with only the transport faked,
    the same way test_composite_server.py drives the real composite callback.

NOT TESTED HERE
    ROS discovery, the MoveToPose action server, the gz pose stream. Those need a
    live stack, and the A-v2 batch owns it.
"""
import math
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from flexcell_interfaces.action import PushObject

from flexcell_skills import push_server as module
from flexcell_skills.contracts import push as contract

BOX_A = [0.220, 0.0, 0.0175]


class _Log:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)


class _GoalHandle:
    def __init__(self, goal, cancel_at=None):
        self.request = goal
        self.goal_id = SimpleNamespace(uuid=[1] * 16)
        self._cancel_at = cancel_at
        self.is_cancel_requested = False
        self.feedback = []
        self.succeeded = self.aborted = self.was_canceled = False

    def publish_feedback(self, fb):
        self.feedback.append(fb)

    def succeed(self):
        self.succeeded = True

    def abort(self):
        self.aborted = True

    def canceled(self):
        self.was_canceled = True


def goal(**overrides):
    g = PushObject.Goal()
    g.request_id = 'test'
    g.object_name = 'target_box_a'
    g.direction.x, g.direction.y, g.direction.z = -1.0, 0.0, 0.0
    g.distance_m = 0.030
    g.contact_height_m = 0.030
    g.overdrive_m = 0.02
    g.motion_profile_id = 'demo_slow'
    g.max_increments = 5
    for key, value in overrides.items():
        setattr(g, key, value)
    return g


def server(positions, reach=(True, 0.006), carry=False):
    """A PushServer with the transport faked and everything else real."""
    node = module.PushServer.__new__(module.PushServer)
    node._seq = 0
    node._admission = threading.Lock()
    node._admission_wait_s = 5.0
    node._params = dict(contract.DEFAULTS)
    node._params['contact_height_m'] = float('nan')
    node._params['increments'] = 5
    node._params['max_increments'] = 10
    node._objects = SimpleNamespace(known=lambda: {'target_box_a', 'target_box_b'})
    node._profiles = ['demo_slow']
    node._default_profile = 'demo_slow'
    node._deadline = 30000
    node._size = [0.035, 0.035, 0.035]
    node._base = 'world'
    node._sample_age = 0.5
    node._sample_timeout = 8.0
    node._log = _Log()
    node.get_logger = lambda: Mock()
    queue = list(positions)

    def measure(_name):
        if len(queue) > 1:
            return list(queue.pop(0)), None
        return list(queue[0]), None

    node._measure = measure
    node._carry_engaged = lambda: (carry, None)
    moves = []

    def call(position, profile, deadline_ms, request_id, cancel_check):
        moves.append(list(position))
        ok, error = reach
        result = SimpleNamespace(outcome=0 if ok else 1, error_code=0,
                                 position_error_m=error,
                                 detail='scripted')
        return result, None

    node._m2p = SimpleNamespace(call=call)
    node.moves = moves
    return node


def test_a_measured_push_maps_every_result_field():
    """A successful push must arrive as SUCCEEDED with its evidence intact."""
    # 10 + 10 + 10 mm of box travel in three increments, then still.
    positions = [BOX_A,
                 [0.210, 0.0, 0.0175], [0.200, 0.0, 0.0175],
                 [0.190, 0.0, 0.0175], [0.190, 0.0, 0.0175],
                 [0.190, 0.0, 0.0175], [0.190, 0.0, 0.0175],
                 [0.190, 0.0, 0.0175]]
    node = server(positions)
    handle = _GoalHandle(goal())
    result = node._execute(handle)
    assert result.outcome == contract.OUTCOME_SUCCEEDED, result.detail
    assert handle.succeeded and not handle.aborted
    assert result.displacement_m == pytest.approx(0.030, abs=1e-6)
    assert result.direction_cos == pytest.approx(1.0, abs=1e-6)
    assert result.contact_made is True and result.contact_lost is False
    assert result.carry_engaged_during is False
    assert result.increments_executed >= 3
    # measured_before/after are Pose messages, not lists.
    assert result.measured_before.position.x == pytest.approx(0.220, abs=1e-9)
    assert result.measured_after.position.x == pytest.approx(0.190, abs=1e-9)
    assert result.measured_before.orientation.w == 1.0


def test_the_measured_saturation_is_reported_as_contact_lost():
    """The archived shape: 23 mm of 30 mm, then the box stops dead."""
    positions = [BOX_A,
                 [0.210, 0.0, 0.0175], [0.200, 0.0, 0.0175],
                 [0.197, 0.0, 0.0175], [0.197, 0.0, 0.0175]]
    node = server(positions)
    handle = _GoalHandle(goal())
    result = node._execute(handle)
    assert result.outcome == contract.OUTCOME_FAILED
    assert result.error_code == contract.ERR_CONTACT_LOST
    assert result.contact_lost is True
    assert handle.aborted


def test_a_zero_displacement_push_is_contact_not_made():
    positions = [BOX_A] + [BOX_A] * 8
    node = server(positions)
    handle = _GoalHandle(goal())
    result = node._execute(handle)
    assert result.error_code == contract.ERR_CONTACT_NOT_MADE
    assert result.contact_made is False


def test_a_nan_cosine_is_logged_as_null_not_as_invalid_json():
    """json.dumps writes NaN, which is not JSON; the log reader rejects it."""
    import json
    positions = [BOX_A] + [BOX_A] * 8
    node = server(positions)
    node._execute(_GoalHandle(goal()))
    record = node._log.records[-1]
    json.dumps(record, allow_nan=False)          # would raise on a NaN
    assert record['direction_cos'] is None


def test_unknown_object_and_bad_profile_are_typed_refusals():
    node = server([BOX_A])
    result = node._execute(_GoalHandle(goal(object_name='ghost')))
    assert result.error_code == contract.ERR_OBJECT_NOT_FOUND
    node = server([BOX_A])
    result = node._execute(_GoalHandle(goal(motion_profile_id='nope')))
    assert result.error_code == contract.ERR_INVALID_GOAL


def test_missing_contact_height_is_refused_by_the_node():
    """NaN parameter + NaN goal = nobody measured the height: refuse."""
    node = server([BOX_A])
    handle = _GoalHandle(goal(contact_height_m=float('nan')))
    result = node._execute(handle)
    assert result.error_code == contract.ERR_INVALID_GOAL
    assert 'contact_height_m' in result.detail
    assert node.moves == []


def _enable_reposition(node):
    node._safe_reposition_enabled = True
    node._reposition_min_height = .18
    node._ee_position = lambda: ([.19, 0., .02], None)


def test_reposition_with_unconfirmed_lift_is_typed_failure_not_default_success():
    node = server([BOX_A] * 20)
    _enable_reposition(node)
    result = node._execute(_GoalHandle(goal()))
    assert result.outcome == contract.OUTCOME_FAILED
    assert result.error_code == contract.ERR_MOTION_FAILED
    assert 'below measured clearance' in result.detail
    assert len(node.moves) == 1


def test_reposition_missing_pose_sends_no_motion():
    node = server([BOX_A] * 20)
    _enable_reposition(node)
    node._ee_position = lambda: (None, 'stale TF')
    result = node._execute(_GoalHandle(goal()))
    assert result.outcome == contract.OUTCOME_FAILED
    assert result.error_code == contract.ERR_MOTION_FAILED
    assert node.moves == []


def test_reposition_cancel_is_typed_canceled_and_sends_no_next_waypoint():
    node = server([BOX_A] * 20)
    _enable_reposition(node)
    handle = _GoalHandle(goal())
    original = node._m2p.call
    def cancel_after_lift(position, **kwargs):
        result = original(position, **kwargs)
        handle.is_cancel_requested = True
        return result
    node._m2p.call = cancel_after_lift
    result = node._execute(handle)
    assert result.outcome == contract.OUTCOME_CANCELED
    assert result.error_code == contract.ERR_CANCELED
    assert handle.was_canceled
    assert len(node.moves) == 1


def test_cancellation_surfaces_as_canceled_not_failed():
    node = server([BOX_A] + [[0.210, 0.0, 0.0175]] * 8)
    handle = _GoalHandle(goal())

    original = node._m2p.call

    def cancel_after_two(position, **kwargs):
        out = original(position, **kwargs)
        if len(node.moves) >= 2:
            handle.is_cancel_requested = True
        return out

    node._m2p.call = cancel_after_two
    result = node._execute(handle)
    assert result.outcome == contract.OUTCOME_CANCELED
    assert result.error_code == contract.ERR_CANCELED
    assert handle.was_canceled


def test_an_exception_becomes_a_typed_failure_never_a_default_success():
    """rclpy's fallback Result has outcome=0, which reads as SUCCEEDED."""
    node = server([BOX_A])

    def explode(_name):
        raise RuntimeError('measurement backend died')

    node._measure = explode
    handle = _GoalHandle(goal())
    result = node._execute(handle)
    assert result.outcome == contract.OUTCOME_FAILED
    assert result.error_code == contract.ERR_INTERNAL
    assert handle.aborted


def test_feedback_reports_the_running_measured_displacement():
    """A caller must be able to see saturation happen, not only its verdict.

    If feedback stayed at 0 until the end, an operator watching a stalled push
    would have no signal at all until the goal aborted.
    """
    positions = [BOX_A,
                 [0.210, 0.0, 0.0175], [0.200, 0.0, 0.0175],
                 [0.190, 0.0, 0.0175], [0.190, 0.0, 0.0175],
                 [0.190, 0.0, 0.0175], [0.190, 0.0, 0.0175]]
    node = server(positions)
    handle = _GoalHandle(goal())
    node._execute(handle)
    displacements = [fb.displacement_m for fb in handle.feedback]
    assert displacements, 'no feedback published'
    assert max(displacements) > 0.0, displacements
    # Monotone: the measured displacement only grows during one push.
    assert displacements == sorted(displacements)


def test_admission_is_released_after_a_crash():
    """A leaked admission lock would wedge the whole skill for the run."""
    node = server([BOX_A])
    node._measure = lambda _n: (_ for _ in ()).throw(RuntimeError('boom'))
    node._execute(_GoalHandle(goal()))
    assert not node._admission.locked()
