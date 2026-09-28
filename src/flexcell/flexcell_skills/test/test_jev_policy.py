#!/usr/bin/env python3
"""Unit tests for JevPolicy + the JevBackend contract (issue #10, ratified ④).

Pure python: the backend is scripted, so decide() is hermetic.  Covers the
ratified contract: Choice over the executor-owned menu, fair state bytes
(exact canonical envelope), typed policy_failure -> FSM fallback on
backend error / OOV / no-world, confidence propagation, backend telemetry,
TypeSafe health probe, and policy-input replay with a Jev policy.
"""

import json
import tempfile
import unittest

from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.contracts.episode import (
    EpisodeRecorder, replay_episode)
from flexcell_skills.decision_policy import (
    ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY, Constraints,
    Decision, FSMPolicy, HistoryRecord, TaskGoal)
from flexcell_skills.jev_backends import (
    LocalReproductionBackend, TypeSafeBackend, make_backend)
from flexcell_skills.jev_policy import JevPolicy, POLICY_FAILURE


def _world_state():
    from test_helpers_world import world_state_msg
    return world_state_msg()


def _goal():
    return TaskGoal('g', 'week1_demo_v1', (('target_box_a', 'zone_1'),))


def _constraints():
    return Constraints(
        frozenset((ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
                   'WAIT', 'ABORT')),
        1, 0.06, 'demo_slow', 0.0)


class _ScriptedBackend:
    name = 'scripted'

    def __init__(self, responses):
        self.responses = list(responses)   # JevResponse or Exception
        self.calls = []

    def health(self):
        return True, 'scripted'

    def classify(self, state, question):
        self.calls.append((state, question))
        r = self.responses.pop(0) if len(self.responses) > 1 \
            else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


def _resp(choice, conf=0.9):
    from types import SimpleNamespace
    return SimpleNamespace(choice=choice, probability=conf,
                           raw={'tokens': 3})


def _drive_jev(policy, recorder, world_text, outcomes):
    """Drive one leg (A) with the recorder capturing the exact inputs; leg
    start has no world (fallback owns it), later decisions see the parsed
    canonical envelope."""
    goal = _goal()
    constraints = _constraints()
    history = []
    verified = 0
    while verified < 1:
        wt = world_text if history else None
        recorder.begin_step(wt, goal, constraints, history)
        world = json.loads(wt) if wt else None
        decision = policy.decide(world, goal, constraints, tuple(history))
        recorder.record_decision(decision, 0)
        oc, ec = outcomes[decision.action].pop(0) \
            if decision.action in outcomes else (0, 0)
        recorder.record_executor_result(outcome=oc, error_code=ec,
                                        evidence_id='ev%d' % len(history))
        history.append(HistoryRecord(decision.action, decision.target, oc,
                                     ec, 1, 7, 'ev%d' % len(history)))
        if decision.action == ACTION_VERIFY and oc == 0:
            verified += 1


class TestJevPolicy(unittest.TestCase):

    def test_valid_choice_becomes_decision_with_confidence(self):
        backend = _ScriptedBackend([_resp('PICK', 0.87)])
        policy = JevPolicy(backend)
        d = policy.decide(_world_state(), _goal(), _constraints(), [])
        self.assertEqual(d.action, ACTION_PICK)
        self.assertEqual(d.target, 'target_box_a')   # plan-order pending leg
        self.assertAlmostEqual(d.confidence, 0.87)
        self.assertEqual(d.reason_code, 'PLAN_NEXT')
        self.assertIn('jev backend=scripted', d.explanation)
        self.assertEqual(policy.stats['invocations'], 1)
        self.assertEqual(policy.stats['fallbacks'], 0)

    def test_state_bytes_are_the_exact_canonical_envelope(self):
        """Fair-bytes rule (§4.4): the backend receives the exact canonical
        envelope bytes, byte-identical across calls and equal to
        serialize_envelope of the same world."""
        backend = _ScriptedBackend([_resp('WAIT'), _resp('WAIT')])
        policy = JevPolicy(backend)
        ws = _world_state()
        policy.decide(ws, _goal(), _constraints(), [])
        policy.decide(ws, _goal(), _constraints(), [])
        s1, s2 = backend.calls[0][0], backend.calls[1][0]
        self.assertEqual(s1, s2)
        self.assertEqual(s1, serialize_envelope(ws))
        # and it must parse back through the version gate
        self.assertIn('"WorldStateSchemaVersion":2', s1)

    def test_backend_error_falls_back_to_fsm(self):
        backend = _ScriptedBackend([RuntimeError('endpoint down')])
        policy = JevPolicy(backend)
        fallback = FSMPolicy()
        d = policy.decide(_world_state(), _goal(), _constraints(), [])
        ref = fallback.decide(_world_state(), _goal(), _constraints(), [])
        # FSM fallback decides; the typed policy_failure rides write-only
        self.assertEqual(d.action, ref.action)
        self.assertEqual(d.target, ref.target)
        self.assertEqual(d.reason_code, ref.reason_code)
        self.assertTrue(d.explanation.startswith(
            'jev %s (backend error)' % POLICY_FAILURE))
        self.assertEqual(policy.stats['fallbacks'], 1)
        self.assertEqual(policy.stats['backend_errors'], 1)

    def test_oov_choice_falls_back_and_is_counted(self):
        backend = _ScriptedBackend([_resp('FLY')])
        policy = JevPolicy(backend)
        d = policy.decide(_world_state(), _goal(), _constraints(), [])
        ref = FSMPolicy().decide(_world_state(), _goal(), _constraints(), [])
        self.assertEqual(d.action, ref.action)
        self.assertTrue(d.explanation.startswith(
            'jev %s (oov choice' % POLICY_FAILURE))
        self.assertEqual(policy.stats['parse_errors'], 1)

    def test_no_world_falls_back_without_invoking_backend(self):
        backend = _ScriptedBackend([])
        policy = JevPolicy(backend)
        d = policy.decide(None, _goal(), _constraints(), [])
        ref = FSMPolicy().decide(None, _goal(), _constraints(), [])
        self.assertEqual(d.action, ref.action)   # leg-start OBSERVE
        self.assertEqual(backend.calls, [])
        self.assertEqual(policy.stats['no_world'], 1)
        self.assertEqual(policy.stats['invocations'], 0)

    def test_abort_and_wait_have_no_target(self):
        backend = _ScriptedBackend([_resp('ABORT'), _resp('WAIT')])
        policy = JevPolicy(backend)
        d1 = policy.decide(_world_state(), _goal(), _constraints(), [])
        d2 = policy.decide(_world_state(), _goal(), _constraints(), [])
        self.assertEqual(d1.action, 'ABORT')
        self.assertEqual(d1.target, '')
        self.assertEqual(d2.action, 'WAIT')

    def test_replay_with_jev_policy_zero_divergence(self):
        """The replay store accepts ANY policy: an episode recorded under
        JevPolicy+scripted backend replays 0-diverged under the same setup."""
        responses = [_resp('PICK', 0.9), _resp('PLACE', 0.8),
                     _resp(ACTION_VERIFY, 0.7)]
        world_text = serialize_envelope(_world_state())
        rec = EpisodeRecorder('week1_demo_v1', 'jev-replay', 'jev', '1.0')
        _drive_jev(JevPolicy(_ScriptedBackend(responses)), rec, world_text,
                   {ACTION_PICK: [(0, 0)], ACTION_PLACE: [(0, 0)],
                    ACTION_VERIFY: [(0, 0)]})
        record = rec.to_dict(final_state={'outcome': '0'})
        self.assertEqual(record['policy']['name'], 'jev')
        results = replay_episode(record, JevPolicy(_ScriptedBackend(
            [_resp('PICK', 0.9), _resp('PLACE', 0.8),
             _resp(ACTION_VERIFY, 0.7)])))
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertTrue(r['ok'], r['detail'])

    def test_stats_surface_telemetry(self):
        backend = _ScriptedBackend([_resp('WAIT', 0.5)])
        policy = JevPolicy(backend)
        policy.decide(_world_state(), _goal(), _constraints(), [])
        self.assertEqual(policy.stats['tokens'], 3)


class TestBackends(unittest.TestCase):

    def test_typesafe_health_unavailable_without_sdk(self):
        ok, detail = TypeSafeBackend().health()
        self.assertFalse(ok)
        self.assertIn('typesafe-sdk not installed', detail)

    def test_local_health_requires_endpoint(self):
        import os
        old = os.environ.pop('FLEXCELL_JEV_ENDPOINT', None)
        try:
            ok, detail = LocalReproductionBackend().health()
            self.assertFalse(ok)
            self.assertIn('FLEXCELL_JEV_ENDPOINT', detail)
        finally:
            if old is not None:
                os.environ['FLEXCELL_JEV_ENDPOINT'] = old

    def test_local_backend_parses_response_contract(self):
        def transport(url, payload, timeout_s):
            self.assertIn('WORLD STATE', payload['prompt'])
            return {'choices': [{'text': '{"choice": "PICK", '
                                           '"confidence": 0.91}'}],
                    'usage': {'total_tokens': 11}}
        backend = LocalReproductionBackend(transport=transport)
        policy = JevPolicy(backend)
        d = policy.decide(_world_state(), _goal(), _constraints(), [])
        self.assertEqual(d.action, ACTION_PICK)
        self.assertAlmostEqual(d.confidence, 0.91)
        self.assertEqual(policy.stats['tokens'], 11)

    def test_local_transport_failure_becomes_policy_failure(self):
        def transport(url, payload, timeout_s):
            raise OSError('connection refused')
        policy = JevPolicy(LocalReproductionBackend(transport=transport))
        d = policy.decide(_world_state(), _goal(), _constraints(), [])
        ref = FSMPolicy().decide(_world_state(), _goal(), _constraints(), [])
        self.assertEqual(d.action, ref.action)
        self.assertEqual(policy.stats['backend_errors'], 1)

    def test_factory(self):
        self.assertIsInstance(make_backend('typesafe'), TypeSafeBackend)
        self.assertIsInstance(make_backend('local'), LocalReproductionBackend)
        with self.assertRaises(ValueError):
            make_backend('quantum')


if __name__ == '__main__':
    unittest.main()
