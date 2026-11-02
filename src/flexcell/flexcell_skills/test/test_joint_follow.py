"""Session monitoring must reject false attachment and missing physics evidence."""
import math
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flexcell_skills.joint_follow import JointFollowMonitor, SnapshotWatch, check_backend_parameter


class Clock:
    def __init__(self): self.now = 1_000_000_000
    def __call__(self): return self.now
    def tick(self, ns=20_000_000): self.now += ns


def frame(clock, parent=None, child=None, attached=True):
    return dict(schema_version=1, monotonic_ns=clock.now, sim_ns=clock.now,
        parent_pose=parent or [0., 0., 0., 0., 0., 0., 1.],
        objects={'target_box_a': dict(pose=child or [.1, 0., 0., 0., 0., 0., 1.],
                                       joint_component=attached)})


def monitor():
    clock = Clock()
    follow = JointFollowMonitor(clock=clock)
    follow.arm('target_box_a', 'a' * 32)
    clock.tick(); follow.feed(frame(clock))
    clock.tick(); follow.feed(frame(clock))
    assert follow.wait_ready()[0]
    return follow, clock


def test_rigid_follow_uses_full_relative_transform_not_world_translation():
    follow, clock = monitor()
    q = [0., 0., math.sqrt(.5), math.sqrt(.5)]
    clock.tick()
    follow.feed(frame(clock, parent=[.2, 0., 0.] + q, child=[.2, .1, 0.] + q))
    assert follow.check()[0]
    assert follow.summary()['max_translation_m'] < 1e-10
    assert follow.summary()['max_rotation_rad'] < 1e-7


def test_attached_claim_with_unfollowed_object_latches_failure():
    follow, clock = monitor()
    clock.tick()
    # A positive 3 cm object rise would pass the legacy rise threshold, while
    # the parent rose 10 cm and the claimed joint flag is still true.
    follow.feed(frame(clock, parent=[0., 0., .1, 0., 0., 0., 1.],
                      child=[.1, 0., .03, 0., 0., 0., 1.], attached=True))
    healthy, reason, evidence = follow.snapshot()
    assert not healthy and evidence['fault'] == reason and 'relative pose' in reason
    assert follow.summary()['max_translation_m'] == pytest.approx(.07)
    clock.tick(); follow.feed(frame(clock))
    assert not follow.check()[0]  # later good observations cannot erase it


@pytest.mark.parametrize('defect', ['detached', 'stale', 'gap', 'nan', 'bad_quaternion', 'reversed'])
def test_missing_or_untrustworthy_physics_never_confirms_follow(defect):
    follow, clock = monitor()
    if defect == 'stale':
        clock.tick(600_000_000)
        assert not follow.check()[0]
        return
    clock.tick(100_000_000 if defect == 'gap' else 20_000_000)
    row = frame(clock)
    if defect == 'detached': row['objects']['target_box_a']['joint_component'] = False
    if defect == 'nan': row['objects']['target_box_a']['pose'][0] = float('nan')
    if defect == 'bad_quaternion': row['parent_pose'][3:] = [0., 0., 0., 0.]
    if defect == 'reversed': row['sim_ns'] -= 30_000_000
    follow.feed(row)
    assert not follow.check()[0]


def test_rotation_only_drift_is_rejected():
    follow, clock = monitor()
    angle = math.radians(2.) / 2
    clock.tick()
    follow.feed(frame(clock, child=[.1, 0., 0., 0., 0., math.sin(angle), math.cos(angle)]))
    assert not follow.check()[0]
    assert follow.summary()['max_rotation_rad'] == pytest.approx(math.radians(2.))


def test_release_transition_is_explicit_and_failed_release_stays_faulted():
    follow, clock = monitor()
    follow.begin_release()
    clock.tick(); follow.feed(frame(clock, attached=False))
    follow.end_release(False)
    assert not follow.check()[0]
    assert follow.summary()['fault'] == 'physical release unconfirmed'
    follow.begin_release(); follow.end_release(True)
    assert not follow.summary()['active']


def test_queued_previous_session_sample_is_not_a_new_reference():
    clock = Clock(); follow = JointFollowMonitor(clock=clock)
    follow.arm('target_box_a', 'a' * 32)
    old = frame(clock); old['monotonic_ns'] -= 1
    follow.feed(old)
    assert follow.summary()['samples'] == 0


def test_snapshot_watch_latches_a_later_physical_follow_rejection():
    response = SimpleNamespace(success=True, session='a' * 32, detail='confirmed',
                               state=SimpleNamespace(engaged=True, object_id='target_box_a'))
    broken = SimpleNamespace(success=False, detail='measured relative pose exceeded follow limits')
    future = Mock(); future.done.return_value = True
    future.result.side_effect = [response, broken]
    client = Mock(); client.wait_for_service.return_value = True; client.call_async.return_value = future
    watch = SnapshotWatch(client, SimpleNamespace(Request=lambda: object()), 'target_box_a', 'a' * 32)
    try:
        assert watch.start()
        deadline = time.monotonic() + 2
        while not watch.problem() and time.monotonic() < deadline:
            time.sleep(.01)
        assert 'relative pose' in watch.problem()
    finally:
        assert watch.close()


def test_backend_mismatch_and_unavailable_parameter_are_not_silent_fallbacks():
    client = Mock()
    client.wait_for_service.return_value = True
    future = client.call_async.return_value
    future.done.return_value = True
    future.result.return_value = SimpleNamespace(values=[SimpleNamespace(type=4, string_value='detachable_joint')])
    request_type = SimpleNamespace(Request=lambda: SimpleNamespace())
    assert check_backend_parameter(client, request_type, 'detachable_joint')[0]
    assert not check_backend_parameter(client, request_type, 'teleport')[0]
    client.wait_for_service.return_value = False
    assert not check_backend_parameter(client, request_type, 'detachable_joint')[0]


def test_release_keeps_sampling_the_attached_tail():
    """The release boundary gate measures the tail after the last pre-release publish."""
    follow, clock = monitor()
    before = follow.summary()
    follow.begin_release()
    clock.tick(); follow.feed(frame(clock))
    clock.tick(); follow.feed(frame(clock))
    during = follow.summary()
    assert during['samples'] == before['samples'] + 2
    assert during['last_sim_ns'] == clock.now
    assert during['releasing'] is True


def test_release_does_not_raise_the_follow_fault_it_would_otherwise_raise():
    follow, clock = monitor()
    follow.begin_release()
    clock.tick(20_000_000)
    follow.feed(frame(clock, parent=[0., 0., 0.] + [0., 0., 0., 1.],
                      child=[.1 + .05, 0., 0., 0., 0., 0., 1.]))
    summary = follow.summary()
    assert summary['fault'] == ''
    assert summary['max_translation_m'] >= .05


def test_detach_during_release_is_recorded_not_faulted():
    follow, clock = monitor()
    follow.begin_release()
    clock.tick()
    follow.feed(frame(clock, attached=False))
    assert follow.summary()['fault'] == ''
    follow.end_release(True)
    assert not follow.summary()['active']
