#!/usr/bin/env python3
"""Offline unit tests for the DecisionPolicy interface + FSMPolicy (issue #4).

Pure python - no ROS imports. Run: python3 test/test_decision_policy.py
"""

import unittest

from flexcell_skills.decision_policy import (
    ACTION_ABORT, ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
    Constraints, DecisionPolicy, FSMPolicy, HistoryRecord, PolicyStateError,
    RC_BUDGET_EXHAUSTED, RC_NON_RECOVERABLE, RC_OBSERVE_FAILED, RC_PLAN_NEXT,
    RC_RECOVERABLE_RETRY, RC_VERIFY_BUDGET_EXHAUSTED, RC_VERIFY_MISMATCH_RETRY,
    RECOVERABLE_PICK_ERRORS, TaskGoal)

GOAL = TaskGoal(
    goal_id='g1', scenario_id='week1_demo_v1',
    assignments=(('target_box_a', 'zone_1'), ('target_box_b', 'zone_2')))
BUDGET1 = Constraints(
    allowed_actions=frozenset(('OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'WAIT', 'ABORT')),
    recovery_budget=1, verify_tolerance_m=0.06,
    motion_profile_id='demo_slow', max_world_age_s=1.5)
BUDGET2 = Constraints(
    allowed_actions=BUDGET1.allowed_actions, recovery_budget=2,
    verify_tolerance_m=0.06, motion_profile_id='demo_slow', max_world_age_s=1.5)

OK = 0


def H(action, target, outcome=OK, error_code=0, attempt=1, revision=3, evidence='e'):
    return HistoryRecord(action=action, target=target, outcome=outcome,
                         error_code=error_code, attempt=attempt,
                         world_revision=revision, evidence_id=evidence)


def history_of(*records):
    return tuple(records)


class TestInterface(unittest.TestCase):

    def test_fsmpolicy_conforms_to_interface(self):
        self.assertIsInstance(FSMPolicy(), DecisionPolicy)
        self.assertEqual(FSMPolicy.name, 'fsm')
        decision = FSMPolicy().decide(None, GOAL, BUDGET1, ())
        self.assertIsInstance(decision, DecisionPolicy.__mro__ and object)
        for field in ('action', 'target', 'confidence', 'reason_code',
                      'explanation', 'evidence_ref'):
            self.assertTrue(hasattr(decision, field))
        self.assertEqual(decision.action, ACTION_OBSERVE)
        self.assertEqual(decision.target, 'target_box_a')
        self.assertTrue(0.0 <= decision.confidence <= 1.0)

    def test_recoverable_error_set_is_frozen_semantics(self):
        self.assertEqual(RECOVERABLE_PICK_ERRORS, frozenset({22, 23, 30}))


class TestCleanSequence(unittest.TestCase):
    """FSMPolicy output reproduces the current task sequence, decision by decision."""

    def setUp(self):
        self.p = FSMPolicy()

    def test_full_clean_run_decision_stream(self):
        d = self.p.decide(None, GOAL, BUDGET1, ())
        self.assertEqual((d.action, d.target, d.reason_code),
                         (ACTION_OBSERVE, 'target_box_a', RC_PLAN_NEXT))

        h = history_of(H(ACTION_OBSERVE, 'target_box_a'))
        self.assertEqual(self.p.decide(None, GOAL, BUDGET1, h).action, ACTION_PICK)

        h += history_of(H(ACTION_PICK, 'target_box_a', OK, 0, 1))
        self.assertEqual(self.p.decide(None, GOAL, BUDGET1, h).action, ACTION_PLACE)

        h += history_of(H(ACTION_PLACE, 'target_box_a', OK, 0, 1))
        self.assertEqual(self.p.decide(None, GOAL, BUDGET1, h).action, ACTION_VERIFY)

        h += history_of(H(ACTION_VERIFY, 'target_box_a', OK, 0, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.target), (ACTION_OBSERVE, 'target_box_b'))

        h += history_of(H(ACTION_OBSERVE, 'target_box_b'))
        h += history_of(H(ACTION_PICK, 'target_box_b', OK, 0, 1))
        h += history_of(H(ACTION_PLACE, 'target_box_b', OK, 0, 1))
        self.assertEqual(self.p.decide(None, GOAL, BUDGET1, h).action, ACTION_VERIFY)

    def test_all_legs_complete_raises(self):
        h = history_of(
            H(ACTION_OBSERVE, 'target_box_a'), H(ACTION_PICK, 'target_box_a', OK, 0, 1),
            H(ACTION_PLACE, 'target_box_a', OK, 0, 1), H(ACTION_VERIFY, 'target_box_a', OK, 0, 1),
            H(ACTION_OBSERVE, 'target_box_b'), H(ACTION_PICK, 'target_box_b', OK, 0, 1),
            H(ACTION_PLACE, 'target_box_b', OK, 0, 1), H(ACTION_VERIFY, 'target_box_b', OK, 0, 1))
        with self.assertRaises(PolicyStateError):
            self.p.decide(None, GOAL, BUDGET1, h)


class TestPickRecovery(unittest.TestCase):

    def setUp(self):
        self.p = FSMPolicy()
        self.leg_a = history_of(H(ACTION_OBSERVE, 'target_box_a'))

    def test_recoverable_failure_triggers_reobserve_retry(self):
        h = self.leg_a + history_of(H(ACTION_PICK, 'target_box_a', 1, 23, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code),
                         (ACTION_OBSERVE, RC_RECOVERABLE_RETRY))
        # after the recovery reobserve: retry with attempt 2
        h += history_of(H(ACTION_OBSERVE, 'target_box_a'))
        self.assertEqual(self.p.decide(None, GOAL, BUDGET1, h).action, ACTION_PICK)

    def test_second_failure_exhausts_budget(self):
        h = self.leg_a + history_of(
            H(ACTION_PICK, 'target_box_a', 1, 23, 1),
            H(ACTION_OBSERVE, 'target_box_a'),
            H(ACTION_PICK, 'target_box_a', 1, 23, 2))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_ABORT, RC_BUDGET_EXHAUSTED))

    def test_budget_2_allows_two_recoveries(self):
        p = FSMPolicy()
        h = self.leg_a + history_of(
            H(ACTION_PICK, 'target_box_a', 1, 23, 1), H(ACTION_OBSERVE, 'target_box_a'),
            H(ACTION_PICK, 'target_box_a', 1, 23, 2), H(ACTION_OBSERVE, 'target_box_a'))
        d = p.decide(None, GOAL, BUDGET2, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_PICK, RC_PLAN_NEXT))
        h += history_of(H(ACTION_PICK, 'target_box_a', 1, 23, 3))
        self.assertEqual(p.decide(None, GOAL, BUDGET2, h).reason_code, RC_BUDGET_EXHAUSTED)

    def test_non_recoverable_error_aborts_immediately(self):
        h = self.leg_a + history_of(H(ACTION_PICK, 'target_box_a', 1, 10, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_ABORT, RC_NON_RECOVERABLE))

    def test_plumbing_failure_is_non_recoverable(self):
        h = self.leg_a + history_of(H(ACTION_PICK, 'target_box_a', 255, -1, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_ABORT, RC_NON_RECOVERABLE))

    def test_recovery_reobserve_failure_aborts(self):
        h = self.leg_a + history_of(
            H(ACTION_PICK, 'target_box_a', 1, 23, 1),
            H(ACTION_OBSERVE, 'target_box_a', 255, -1, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_ABORT, RC_OBSERVE_FAILED))


class TestPlaceAndVerify(unittest.TestCase):

    def setUp(self):
        self.p = FSMPolicy()
        self.through_pick = history_of(
            H(ACTION_OBSERVE, 'target_box_a'), H(ACTION_PICK, 'target_box_a', OK, 0, 1))

    def test_place_failure_aborts(self):
        h = self.through_pick + history_of(H(ACTION_PLACE, 'target_box_a', 1, 25, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_ABORT, RC_NON_RECOVERABLE))

    def test_verify_mismatch_triggers_reobserve_reverify(self):
        h = self.through_pick + history_of(
            H(ACTION_PLACE, 'target_box_a', OK, 0, 1),
            H(ACTION_VERIFY, 'target_box_a', 1, 0, 1))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code),
                         (ACTION_OBSERVE, RC_VERIFY_MISMATCH_RETRY))
        # frozen behavior: the verify-path reobserve result is IGNORED (even a
        # plumbing failure) - the re-verify decides
        h += history_of(H(ACTION_OBSERVE, 'target_box_a', 255, -1, 1))
        self.assertEqual(self.p.decide(None, GOAL, BUDGET1, h).action, ACTION_VERIFY)
        h += history_of(H(ACTION_VERIFY, 'target_box_a', 1, 0, 2))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code),
                         (ACTION_ABORT, RC_VERIFY_BUDGET_EXHAUSTED))

    def test_verify_recovery_then_success_completes_leg(self):
        h = self.through_pick + history_of(
            H(ACTION_PLACE, 'target_box_a', OK, 0, 1),
            H(ACTION_VERIFY, 'target_box_a', 1, 0, 1),
            H(ACTION_OBSERVE, 'target_box_a'))
        h += history_of(H(ACTION_VERIFY, 'target_box_a', OK, 0, 2))
        d = self.p.decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.target), (ACTION_OBSERVE, 'target_box_b'))


class TestObserveFailure(unittest.TestCase):

    def test_leg_start_observe_failure_aborts(self):
        h = history_of(H(ACTION_OBSERVE, 'target_box_a', 255, -1, 1))
        d = FSMPolicy().decide(None, GOAL, BUDGET1, h)
        self.assertEqual((d.action, d.reason_code), (ACTION_ABORT, RC_OBSERVE_FAILED))


class TestReplayGuard(unittest.TestCase):

    def test_unexpected_history_shape_raises(self):
        h = history_of(H(ACTION_PICK, 'target_box_a', OK, 0, 1))  # no observe first
        with self.assertRaises(PolicyStateError):
            FSMPolicy().decide(None, GOAL, BUDGET1, h)


if __name__ == '__main__':
    unittest.main()
