"""Mainline route checks: Jev acceptance, LLM escalation and safe degradation."""
import unittest

from flexcell_skills.decision_policy import Constraints, Decision, TaskGoal
from flexcell_skills.hybrid_policy import HybridRouter
from flexcell_skills.contracts.injection import InjectionLifecycle


class Policy:
    def __init__(self, name, decision):
        self.name, self.decision, self.calls = name, decision, 0

    def decide(self, *args):
        self.calls += 1
        return self.decision


class TestHybrid(unittest.TestCase):
    def setUp(self):
        self.goal = TaskGoal('g', 's', (('a', 'z'),))
        self.constraints = Constraints(frozenset(('OBSERVE', 'PICK', 'PLACE',
                                                 'VERIFY', 'WAIT', 'ABORT')),
                                       1, 0.06, 'demo_slow', 0.0)
        self.world = {'world_state': {'objects': [{'name': 'a', 'available': True}],
                                     'carry': {'engaged': False}}}

    def route(self, fast, slow):
        f, s = Policy('jev', fast), Policy('llm', slow)
        router = HybridRouter(f, s, threshold=0.7)
        return router.decide(self.world, self.goal, self.constraints, ()), router, f, s

    def test_high_confidence_fast_path(self):
        d, r, f, s = self.route(Decision('PICK', 'a', 0.9), Decision('WAIT', ''))
        self.assertEqual(d.action, 'PICK')
        self.assertEqual(d.policy_trace['source'], 'jev')
        self.assertEqual(s.calls, 0)

    def test_low_confidence_escalates(self):
        d, r, f, s = self.route(Decision('PICK', 'a', 0.5), Decision('OBSERVE', 'a'))
        self.assertEqual(d.policy_trace['source'], 'llm')
        self.assertEqual(r.stats['escalations'], 1)

    def test_invalid_fast_proposal_escalates_even_at_confidence_one(self):
        d, r, f, s = self.route(Decision('PLACE', 'a', 1.0), Decision('OBSERVE', 'a'))
        self.assertEqual(d.policy_trace['source'], 'llm')
        self.assertEqual(r.stats['rejected_proposals'], 1)

    def test_two_invalid_proposals_fall_back(self):
        d, r, f, s = self.route(Decision('PICK', 'unknown'), Decision('PLACE', 'a'))
        self.assertEqual(d.action, 'OBSERVE')
        self.assertTrue(d.policy_trace['fallback'])
        self.assertEqual(r.stats['fallbacks'], 1)

    def test_model_fallback_confidence_does_not_count_as_fast_success(self):
        d, r, f, s = self.route(
            Decision('OBSERVE', 'a', policy_trace={'source': 'fsm', 'fallback': True}),
            Decision('OBSERVE', 'a'))
        self.assertEqual(d.policy_trace['source'], 'llm')

    def test_bootstrap_never_calls_models(self):
        fast, slow = Policy('jev', None), Policy('llm', None)
        router = HybridRouter(fast, slow)
        d = router.decide(None, self.goal, self.constraints, ())
        self.assertEqual(d.action, 'OBSERVE')
        self.assertEqual(fast.calls + slow.calls, 0)

    def test_s3_injection_targets_only_b_first_attempt(self):
        injection = InjectionLifecycle()
        injection.on_request('s3@b:once#r1')
        self.assertIsNone(injection.on_pick_attempt('a'))
        self.assertIsNotNone(injection.on_pick_attempt('b'))
        self.assertIsNone(injection.on_pick_attempt('b'))
        self.assertEqual(injection.snapshot()['applied_count'], 1)


if __name__ == '__main__':
    unittest.main()
