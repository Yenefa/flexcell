"""Controller uncertainty must stop the executor, rather than permit recovery motion."""
from types import SimpleNamespace as NS
from unittest.mock import Mock
import time

import pytest
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from moveit_msgs.msg import RobotTrajectory
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration
from builtin_interfaces.msg import Time

from flexcell_skills import mtc_motion as module


def trajectory():
    result = JointTrajectory(joint_names=['joint1', 'joint2', 'joint3', 'joint4'])
    result.points = [JointTrajectoryPoint(positions=[0.] * 4, time_from_start=Duration(sec=t)) for t in (0, 1)]
    return result


@pytest.mark.parametrize('defect', ['duplicate_joint', 'missing_joint', 'nan', 'backwards', 'empty', 'bad_velocity'])
def test_untrusted_trajectory_rejected(defect):
    value = trajectory()
    if defect == 'duplicate_joint': value.joint_names[0] = 'joint2'
    elif defect == 'missing_joint': value.joint_names.pop()
    elif defect == 'nan': value.points[1].positions[2] = float('nan')
    elif defect == 'backwards': value.points[1].time_from_start.sec = 0
    elif defect == 'empty': value.points = []
    elif defect == 'bad_velocity': value.points[1].velocities = [0.]
    with pytest.raises(ValueError):
        module.validate_trajectory(value)


def adapter():
    client = module.MtcMotionClient.__new__(module.MtcMotionClient)
    client.blocked = False
    client.audit = []
    client.plans = [([.2, 0., .2], RobotTrajectory(joint_trajectory=trajectory()))]
    client.registration = Mock()
    client.registration.call_async.return_value.result.return_value = NS(success=True)
    client.executor = Mock()
    return client


def call(client):
    return client.call([.2, 0., .2], profile='demo_slow', deadline_ms=30000, request_id='trial-lift')


def test_lost_registration_never_dispatches_motion(monkeypatch):
    client = adapter()
    monkeypatch.setattr(module, 'wait_future', lambda *_: 'timeout')
    result, error = call(client)
    assert result is None and 'no motion dispatched' in error
    client.executor.call.assert_not_called()


def test_unknown_executor_result_latches_adapter(monkeypatch):
    client = adapter()
    monkeypatch.setattr(module, 'wait_future', lambda *_: 'done')
    result = module.MoveToPose.Result()
    result.outcome = result.OUTCOME_STATE_UNKNOWN
    result.error_code = result.ERR_STATE_UNKNOWN
    result.detail = 'controller terminal result missing'
    client.executor.call.return_value = (result, None)
    with pytest.raises(module.MotionTerminalUnknown):
        call(client)
    assert client.blocked
    with pytest.raises(module.MotionTerminalUnknown):
        call(client)
    assert client.executor.call.call_count == 1


def test_handoff_preserves_target_and_whitelisted_profile(monkeypatch):
    client = adapter()
    monkeypatch.setattr(module, 'wait_future', lambda *_: 'done')
    result = module.MoveToPose.Result()
    client.executor.call.return_value = (result, None)
    assert call(client)[0] is result
    request = client.registration.call_async.call_args.args[0]
    assert request.target.header.frame_id == 'world'
    assert request.motion_profile_id == 'demo_slow'
    assert request.request_id.startswith('mtc-')
    assert client.executor.call.call_args.kwargs['request_id'] == request.request_id


def test_planning_uses_stamped_world_poses_and_never_executes(monkeypatch):
    client = adapter()
    client.planner = Mock()
    client.planner.call_async.return_value.result.return_value = NS(success=True, detail='planned',
        trajectories=[RobotTrajectory(joint_trajectory=trajectory()) for _ in range(3)])
    monkeypatch.setattr(module, 'wait_future', lambda *_: 'done')
    ok, _ = client.prepare('PICK', 'target_box_a', [.2, 0., .0175],
        [[.2, 0., z] for z in (.22, .16, .26)], 'demo_slow', 30000)
    assert ok
    request = client.planner.call_async.call_args.args[0]
    assert request.object_pose.header.frame_id == 'world'
    assert all(target.header.frame_id == 'world' for target in request.targets)
    client.executor.call.assert_not_called()


def test_consumed_handoff_cannot_be_replayed():
    from flexcell_skills.move_to_pose_server import MoveToPoseServer
    from flexcell_interfaces.srv import RegisterMtcTrajectory
    import threading
    request = RegisterMtcTrajectory.Request(request_id='mtc-' + 'a' * 32,
        target=module.stamped([.2, 0., .2]), motion_profile_id='demo_slow',
        trajectory=RobotTrajectory(joint_trajectory=trajectory()))
    server = MoveToPoseServer.__new__(MoveToPoseServer)
    server._registered_mtc = (request, time.monotonic() + 5)
    server._joint_state = lambda: (JointState(name=['joint1', 'joint2', 'joint3', 'joint4'], position=[0.] * 4), .01)
    goal = module.MoveToPose.Goal(request_id=request.request_id,
        target=request.target, motion_profile_id=request.motion_profile_id)
    assert server._consume_mtc(goal) is request.trajectory
    with pytest.raises(ValueError, match='missing or expired'):
        server._consume_mtc(goal)
    # Registration shares the legacy motion admission lock, not a second controller owner.
    server._admission = threading.Lock()
    server._admission.acquire()
    response = server._register_mtc(request, RegisterMtcTrajectory.Response())
    server._admission.release()
    assert not response.success and 'busy' in response.detail


def test_executor_exception_before_motion_returns_declared_failure_code():
    from flexcell_skills.move_to_pose_server import MoveToPoseServer
    import threading
    server = MoveToPoseServer.__new__(MoveToPoseServer)
    server._new_evidence = lambda _: ('fixture', 'fixture-evidence')
    server._admission = threading.Lock()
    server._enforce_ori = False
    server._feedback = Mock(side_effect=ValueError('broken before execution'))
    server._log = Mock()
    goal = NS(request=module.MoveToPose.Goal(target=module.stamped([.2, 0., .2])),
              goal_id=NS(uuid=[0] * 16), abort=Mock())
    result = server._execute(goal)
    assert result.outcome == result.OUTCOME_FAILED
    assert result.error_code == result.ERR_INVALID_GOAL
    assert result.evidence_id == 'fixture-evidence'
    goal.abort.assert_called_once()
