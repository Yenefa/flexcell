"""A joint session must be anchored on a measured, at-rest pre-attach transform."""
import math
import time

import pytest
from flexcell_skills.joint_follow import JointFollowMonitor, PrepositionLatch


class Clock:
    def __init__(self): self.now = 1_000_000_000
    def __call__(self): return self.now
    def tick(self, ns=20_000_000): self.now += ns


def frame(clock, parent=None, child=None, attached=False):
    return dict(schema_version=1, monotonic_ns=clock.now, sim_ns=clock.now,
                parent_pose=parent or [0., 0., 0., 0., 0., 0., 1.],
                objects={'target_box_a': dict(pose=child or [.1, 0., 0., 0., 0., 0., 1.],
                                              joint_component=attached),
                         'target_box_b': dict(pose=[.1, .3, 0., 0., 0., 0., 1.],
                                              joint_component=False)})


def steady(latch, clock, count=5):
    for _ in range(count):
        clock.tick()
        latch.feed(frame(clock))
    return latch


def test_at_rest_hold_yields_the_averaged_pre_attach_reference():
    clock = Clock()
    latch = PrepositionLatch(clock=clock)
    steady(latch, clock)
    ok, reference, evidence = latch.take('target_box_a', timeout=.1)
    assert ok
    assert reference[:3] == pytest.approx([.1, 0., 0.]) and reference[3:] == pytest.approx([0., 0., 0., 1.])
    assert evidence['samples'] == 5 and evidence['window_ns'] == 80_000_000
    assert evidence['spread_m'] < 1e-12
    assert evidence['contact_freedom'] == 'NOT_OBSERVABLE_ON_POSE_TOPIC'


def test_moving_arm_is_not_a_positioned_reference():
    clock = Clock()
    latch = PrepositionLatch(clock=clock)
    for step in range(5):
        clock.tick()
        latch.feed(frame(clock, parent=[0., 0., .002 * step, 0., 0., 0., 1.]))
    ok, reference, detail = latch.take('target_box_a', timeout=.05)
    assert not ok and reference is None and 'not at rest' in detail


def test_attachment_discards_the_detached_history():
    clock = Clock()
    latch = PrepositionLatch(clock=clock)
    steady(latch, clock, 4)
    clock.tick()
    latch.feed(frame(clock, attached=True))
    clock.tick()
    latch.feed(frame(clock))
    ok, _, detail = latch.take('target_box_a', timeout=.05)
    assert not ok and 'hold of 5 samples' in detail


def test_stale_hold_is_refused_at_engage_time():
    clock = Clock()
    latch = PrepositionLatch(clock=clock)
    steady(latch, clock)
    clock.now += 400_000_000  # the arm has been idle far longer than the declared age
    ok, reference, detail = latch.take('target_box_a', timeout=.05)
    assert not ok and reference is None and 'stale' in detail


def test_binding_must_not_move_the_declared_reference():
    reference = [.1, 0., 0., 0., 0., 0., 1.]
    clock = Clock()
    follow = JointFollowMonitor(clock=clock)
    follow.arm('target_box_a', 'a' * 32, reference, dict(samples=5, spread_m=0., spread_rad=0.,
                                                         contact_freedom='NOT_OBSERVABLE_ON_POSE_TOPIC'))
    clock.tick()
    follow.feed(frame(clock, attached=True))
    clock.tick()
    follow.feed(frame(clock, attached=True))
    ok, reason, evidence = follow.snapshot()
    assert ok and evidence['reference_source'] == 'preposition'
    assert evidence['attach_jump_translation_m'] < 1e-12
    clock.tick()
    follow.feed(frame(clock, parent=[0., 0., .003, 0., 0., 0., 1.], attached=True))
    ok, reason, evidence = follow.snapshot()
    assert not ok and 'relative pose' in reason


def test_a_declared_reference_requires_its_own_evidence():
    follow = JointFollowMonitor(clock=Clock())
    with pytest.raises(ValueError):
        follow.arm('target_box_a', 'a' * 32, [.1, 0., 0., 0., 0., 0., 1.], None)


def test_legacy_session_without_a_reference_still_latches_the_first_attachment():
    clock = Clock()
    follow = JointFollowMonitor(clock=clock)
    follow.arm('target_box_a', 'a' * 32)
    clock.tick(); follow.feed(frame(clock, attached=True))
    clock.tick(); follow.feed(frame(clock, attached=True))
    ok, _, evidence = follow.snapshot()
    assert ok and evidence['reference_source'] == 'first_attached'
    assert evidence['attach_jump_translation_m'] is None
