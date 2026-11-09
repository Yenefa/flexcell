#!/usr/bin/env python3
"""Offline unit tests for the executor skill post-conditions (issue #20, M2.2-0).

Planted-violation suite: every check must pass a genuine success shape,
reject the default-Result phantom shape (outcome=0, markers false - the
rclpy crash-fallback Week-1 PLACE ghost), and stay silent on non-success
outcomes.  Pure python - no ROS imports.
Run: python3 test/test_skill_contract.py
"""

import unittest
from types import SimpleNamespace

from flexcell_skills.skill_contract import check_pick, check_place, check_verify

SUCCESS = 0
FAILED = 1
MISMATCH = 1

PLACE_AT = (0.12, -0.15, 0.0175)
TOL = 0.06


def pick_result(outcome=SUCCESS, grasp_attached=True, **kw):
    return SimpleNamespace(outcome=outcome, grasp_attached=grasp_attached,
                           evidence_id='e1', detail='picked', **kw)


def place_result(outcome=SUCCESS, released=True, after=PLACE_AT, **kw):
    pose = SimpleNamespace(
        position=SimpleNamespace(x=after[0], y=after[1], z=after[2]))
    return SimpleNamespace(outcome=outcome, released=released,
                           object_pose_after=pose, evidence_id='e1',
                           detail='placed', **kw)


def verify_result(outcome=SUCCESS, has_measured_pose=True, **kw):
    return SimpleNamespace(outcome=outcome, has_measured_pose=has_measured_pose,
                           position_error_m=0.005, evidence_id='e1', **kw)


class TestPickPostCondition(unittest.TestCase):

    def test_genuine_success_passes(self):
        self.assertIsNone(check_pick(pick_result()))

    def test_planted_phantom_rejected(self):
        v = check_pick(pick_result(grasp_attached=False))
        self.assertIsNotNone(v)
        self.assertIn('grasp_attached', v)

    def test_failure_outcome_not_checked(self):
        self.assertIsNone(check_pick(pick_result(outcome=FAILED,
                                                 grasp_attached=False)))

    def test_default_result_shape_rejected(self):
        # rclpy crash fallback: default Result, outcome=0, every marker false
        self.assertIsNotNone(check_pick(SimpleNamespace(outcome=0)))


class TestPlacePostCondition(unittest.TestCase):

    def test_genuine_success_passes(self):
        self.assertIsNone(check_place(place_result(), PLACE_AT, TOL))

    def test_planted_phantom_rejected(self):
        v = check_place(place_result(released=False), PLACE_AT, TOL)
        self.assertIsNotNone(v)
        self.assertIn('released', v)

    def test_pose_outside_tolerance_rejected(self):
        r = place_result(after=(0.30, 0.20, 0.0175))
        v = check_place(r, PLACE_AT, TOL)
        self.assertIsNotNone(v)
        self.assertIn('settled', v)

    def test_pose_check_skipped_without_target(self):
        self.assertIsNone(check_place(place_result(), None, None))

    def test_default_result_shape_rejected(self):
        self.assertIsNotNone(check_place(SimpleNamespace(outcome=0),
                                         PLACE_AT, TOL))


class TestVerifyPostCondition(unittest.TestCase):

    def test_genuine_success_passes(self):
        self.assertIsNone(check_verify(verify_result()))

    def test_planted_phantom_rejected(self):
        v = check_verify(verify_result(has_measured_pose=False))
        self.assertIsNotNone(v)
        self.assertIn('has_measured_pose', v)

    def test_mismatch_outcome_not_checked(self):
        self.assertIsNone(check_verify(verify_result(outcome=MISMATCH,
                                                    has_measured_pose=False)))

    def test_default_result_shape_rejected(self):
        self.assertIsNotNone(check_verify(SimpleNamespace(outcome=0)))


if __name__ == '__main__':
    unittest.main()
