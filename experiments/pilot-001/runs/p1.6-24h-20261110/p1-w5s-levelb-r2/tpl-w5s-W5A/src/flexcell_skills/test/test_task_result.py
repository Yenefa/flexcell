"""Typed abort causes must survive model explanations without changing codes."""
import unittest

from flexcell_skills.contracts.error_codes import task_abort_error_code
from flexcell_skills.contracts.skill_result import previous_skill_result
from flexcell_skills.contracts.task_result import task_abort_detail
from flexcell_skills.decision_policy import (
    Constraints, HistoryRecord, TaskGoal)
from flexcell_skills.jev_policy import JevBackend, JevPolicy, JevResponse


class TestTaskAbortDetail(unittest.TestCase):
    def test_model_explanation_cannot_hide_the_last_place_motion_failure(self):
        previous = previous_skill_result('PLACE', 1, 30)
        for explanation in ['jev backend=clef prob=0.473 raw={}',
                            'LLM selected abort', 'place failed']:
            with self.subTest(explanation=explanation):
                detail = task_abort_detail('NON_RECOVERABLE', explanation,
                                           ['PLACE_A:FAIL'], previous)
                self.assertIn(explanation, detail)
                self.assertIn('previous_skill=PLACE cause=ERR_MOTION_FAILED', detail)
                self.assertIn('legacy_error_code=30', detail)
                self.assertEqual(task_abort_error_code('NON_RECOVERABLE'), 50)

    def test_budget_abort_retains_51_and_underlying_grasp_code(self):
        detail = task_abort_detail('BUDGET_EXHAUSTED', 'model abort', [],
                                   previous_skill_result('PICK', 1, 23))
        self.assertIn('cause=ERR_GRASP_FAILED', detail)
        self.assertEqual(task_abort_error_code('BUDGET_EXHAUSTED'), 51)

    def test_verify_mismatch_is_typed_despite_legacy_zero(self):
        detail = task_abort_detail('VERIFY_BUDGET_EXHAUSTED', 'model abort', [],
                                   previous_skill_result('VERIFY', 1, 0))
        self.assertIn('cause=ERR_VERIFY_FAILED legacy_error_code=0', detail)
        self.assertEqual(task_abort_error_code('VERIFY_BUDGET_EXHAUSTED'), 51)

    def test_plumbing_timeout_does_not_invent_a_skill_reply(self):
        detail = task_abort_detail('NON_RECOVERABLE', 'timeout', [],
                                   previous_skill_result('PICK', 255, -1))
        self.assertIn('cause=ERR_TIMEOUT legacy_error_code=-1', detail)

    def test_unknown_legacy_code_keeps_the_mapping_warning(self):
        detail = task_abort_detail('NON_RECOVERABLE', 'abort', [],
                                   previous_skill_result('PLACE', 1, 999))
        self.assertIn('cause=ERR_INTERNAL legacy_error_code=999', detail)
        self.assertIn('mapping_warning=unmapped legacy', detail)

    def test_no_previous_failure_keeps_the_original_detail(self):
        expected = 'policy abort (MODEL_STOP): model abort (trace=OBSERVE_A:OK)'
        for previous in [None, previous_skill_result('OBSERVE', 0, 0)]:
            self.assertEqual(task_abort_detail('MODEL_STOP', 'model abort',
                                               ['OBSERVE_A:OK'], previous), expected)

    def test_real_jev_decision_with_failed_place_retains_source_and_cause(self):
        class AbortBackend(JevBackend):
            name = 'synthetic-abort'

            def health(self):
                return True, 'synthetic backend'

            def classify(self, state, question):
                return JevResponse('ABORT', 0.473, {'tokens': 7})

        policy = JevPolicy(AbortBackend())
        history = (
            HistoryRecord('OBSERVE', 'a', 0, 0, 1, 1, 'observe'),
            HistoryRecord('PICK', 'a', 0, 0, 1, 1, 'pick'),
            HistoryRecord('PLACE', 'a', 1, 30, 1, 1, 'place'),
        )
        decision = policy.decide({}, TaskGoal('g', 'S4', (('a', 'zone_1'),)),
                                 Constraints(frozenset(['ABORT']), 1, 0.06,
                                             'demo_slow', 0.0), history)
        self.assertEqual(decision.action, 'ABORT')
        self.assertFalse(decision.policy_trace['fallback'])
        self.assertNotIn('ERR_MOTION_FAILED', decision.explanation)
        detail = task_abort_detail(decision.reason_code, decision.explanation, [],
                                   previous_skill_result('PLACE', 1, 30))
        self.assertIn('ERR_MOTION_FAILED', detail)
        self.assertEqual(task_abort_error_code(decision.reason_code), 50)
