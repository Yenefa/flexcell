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
    client.plans = [([.2, 0., .2], RobotTrajectory(joint_trajectory=trajectory()), [.2, 0., .2])]
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


def test_object_center_plan_hands_explicit_ee_endpoint_to_only_motion_owner(monkeypatch):
    client = adapter()
    client.planner = Mock()
    logical = [[.12, -.15, z] for z in (.1675, .0675, .1675)]
    endpoints = [[.18, -.21, z] for z in (.28, .18, .28)]
    client.planner.call_async.return_value.result.return_value = NS(success=True, detail='planned',
        trajectories=[RobotTrajectory(joint_trajectory=trajectory()) for _ in range(3)],
        executor_targets=[module.stamped(p) for p in endpoints])
    client.executor.call.return_value = (module.MoveToPose.Result(), None)
    monkeypatch.setattr(module, 'wait_future', lambda *_: 'done')
    assert client.prepare('PLACE', 'target_box_a', [.25, 0., .12], logical, 'demo_slow', 30000,
        attached_object_targets=True, object_orientation=[0., 0., 0., 1.])[0]
    assert client.planner.call_async.call_args.args[0].attached_object_targets
    client.call(logical[0], profile='demo_slow', deadline_ms=30000, request_id='hover')
    assert client.executor.call.call_args.args[0] == endpoints[0]
    assert client.registration.call_async.call_args.args[0].target == module.stamped(endpoints[0])
    assert client.audit[0]['target'] == logical[0]
    assert client.audit[0]['executor_target'] == endpoints[0]


@pytest.mark.parametrize('defect', ['missing', 'frame', 'nonfinite'])
def test_object_target_cannot_fall_back_to_ee_target_when_endpoint_metadata_is_bad(monkeypatch, defect):
    client = adapter()
    client.planner = Mock()
    endpoints = [module.stamped([.2, 0., .2]) for _ in range(3)]
    if defect == 'missing': endpoints.pop()
    elif defect == 'frame': endpoints[0].header.frame_id = 'camera'
    else: endpoints[0].pose.position.x = float('nan')
    client.planner.call_async.return_value.result.return_value = NS(success=True, detail='planned',
        trajectories=[RobotTrajectory(joint_trajectory=trajectory()) for _ in range(3)],
        executor_targets=endpoints)
    monkeypatch.setattr(module, 'wait_future', lambda *_: 'done')
    assert not client.prepare('PLACE', 'target_box_a', [.2, 0., .12],
        [[.12, -.15, z] for z in (.1675, .0675, .1675)], 'demo_slow', 30000,
        attached_object_targets=True)[0]
    assert client.plans == []
    client.executor.call.assert_not_called()
    client.registration.call_async.assert_not_called()


@pytest.mark.parametrize('observation', ['missing', 'outside', 'nonfinite'])
def test_joint_place_keeps_attachment_when_pre_release_physical_sample_is_unusable(monkeypatch, observation):
    import threading
    from flexcell_skills import place_server as place
    server = place.PlaceServer.__new__(place.PlaceServer)
    server._seq = 0
    server._admission = threading.Lock()
    server._default_profile = 'demo_slow'
    server._profiles = ['demo_slow']
    server._backend_consistent = lambda: (True, '')
    server._scene = Mock()
    server._scene.is_attached.return_value = (True, '')
    server._carry_backend = 'detachable_joint'
    server._carry_query = Mock()
    server._carry_release = Mock()
    server._gripper = Mock()
    server._clearance, server._hover, server._carry, server._retreat = .05, .1, .16, .1
    server._tol, server._deadline = .06, 30000
    server._mtc = Mock(audit=[])
    server._mtc.prepare.return_value = (True, 'planned')
    server._feedback = Mock()
    server._log = Mock()
    server._motion = Mock(return_value=(NS(outcome=0, error_code=0), 0, 'OK'))
    watch = Mock()
    watch.problem.return_value = ''
    watch.summary.return_value = {}
    monkeypatch.setattr(place, 'SnapshotWatch', lambda *_: watch)
    after = (([.25, -.25, .0675], [0., 0., 0., 1.]), None)
    if observation == 'missing': after = (None, 'stream stale')
    elif observation == 'nonfinite': after[0][0][0] = float('nan')
    sampler = Mock(side_effect=[(([.25, 0., .12], [0., 0., 0., 1.]), None), after])
    monkeypatch.setattr(place, 'sample_gz_pose', sampler)
    goal = place.PlaceObject.Goal(object_name='target_box_a',
        place_pose=module.stamped([.12, -.15, .0175]), motion_profile_id='demo_slow')
    handle = NS(request=goal, is_cancel_requested=False, abort=Mock(), succeed=Mock(), canceled=Mock())
    result = server._execute(handle)
    assert result.outcome == result.OUTCOME_FAILED and result.error_code == result.ERR_PLACE_FAILED
    assert not result.released and 'carry held' in result.detail
    assert server._motion.call_count == 2
    assert server._mtc.prepare.call_args.kwargs['attached_object_targets']
    assert server._mtc.prepare.call_args.args[3][1] == [.12, -.15, .0675]
    server._carry_release.call_async.assert_not_called()
    server._scene.detach_to_world.assert_not_called()
    server._gripper.command.assert_not_called()
    handle.abort.assert_called_once()


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
