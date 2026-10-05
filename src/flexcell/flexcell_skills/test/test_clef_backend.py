"""ClefBackend contract tests (transport injected; no server, no network)."""
import os
import socket
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from flexcell_skills.jev_backends import ClefBackend, make_backend

QUESTION = SimpleNamespace(
    prompt='Choose the next action for the pending leg.',
    context='last=SUCCEEDED(attempt=1) pending=PICK(target_box_a)',
    options=(SimpleNamespace(action='OBSERVE', criteria='world stale or object unknown'),
             SimpleNamespace(action='PICK', criteria='object observed and not carried'),
             SimpleNamespace(action='ABORT', criteria='budget spent or unrecoverable')))
STATE = '{"schema_version":2,"robot":{"joint_positions_deg":[0,0,0,0]}}'


class TestClefBackend(unittest.TestCase):

    def test_payload_shape_and_parse_per_question_key(self):
        seen = {}

        def transport(url, payload, timeout_s):
            seen['url'], seen['payload'], seen['timeout'] = url, payload, timeout_s
            return {'answers': {'next_action': {
                        'type': 'choice', 'choice': 'PICK', 'confidence': 0.91,
                        'probabilities': {'OBSERVE': 0.05, 'PICK': 0.87,
                                          'ABORT': 0.08}}},
                    'usage': {'input_tokens': 486, 'output_tokens': 3}}

        os.environ['FLEXCELL_JEV_ENDPOINT'] = 'http://127.0.0.1:11434/v1/systemone'
        os.environ['FLEXCELL_JEV_MODEL'] = 'clef-flash'
        os.environ['FLEXCELL_JEV_MODEL_SHA256'] = 'abc123'
        try:
            resp = ClefBackend(transport=transport).classify(STATE, QUESTION)
        finally:
            for key in ('FLEXCELL_JEV_ENDPOINT', 'FLEXCELL_JEV_MODEL',
                        'FLEXCELL_JEV_MODEL_SHA256'):
                os.environ.pop(key, None)
        self.assertEqual(seen['url'], 'http://127.0.0.1:11434/v1/systemone')
        self.assertEqual(seen['payload']['model'], 'clef-flash')
        self.assertEqual(seen['payload']['state'], STATE)
        question = seen['payload']['questions']['next_action']
        self.assertEqual(question['type'], 'choice')
        self.assertIn('OBSERVE -> PICK -> PLACE -> VERIFY', question['instructions'])
        self.assertIn('Context:', question['instructions'])
        self.assertTrue(question['criteria']['OBSERVE']
                        .startswith('world stale or object unknown'))
        self.assertIn('refresh the world snapshot', question['criteria']['OBSERVE'])
        self.assertIn('retry budget spent', question['criteria']['ABORT'])
        self.assertEqual(resp.choice, 'PICK')
        # routing signal = chosen option's probability, not the mass
        # concentration reported in `confidence`
        self.assertAlmostEqual(resp.probability, 0.87)
        self.assertEqual(resp.raw['backend'], 'clef')
        # injected transport = offline test: no live model identity (repo
        # convention shared with LocalReproductionBackend)
        self.assertIsNone(resp.raw['model_sha256'])
        self.assertAlmostEqual(resp.raw['concentration'], 0.91)
        self.assertEqual(resp.raw['output_tokens'], 3)
        self.assertEqual(resp.raw['tokens'], 489)

    def test_classifier_with_zero_output_records_input_tokens(self):
        transport = lambda *args: {'answers': {'next_action': {
            'choice': 'PICK', 'probabilities': {'PICK': .9}}},
            'usage': {'input_tokens': 486, 'output_tokens': 0}}
        self.assertEqual(ClefBackend(transport=transport).classify(
            STATE, QUESTION).raw['tokens'], 486)

    def test_health_rejects_configured_but_closed_socket(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            # Bound without listen: deterministic refused connection.
            endpoint = 'http://127.0.0.1:%d/v1/systemone' % server.getsockname()[1]
            with patch.dict(os.environ, FLEXCELL_JEV_ENDPOINT=endpoint):
                ok, detail = ClefBackend().health()
        self.assertFalse(ok)
        self.assertIn('TCP', detail)

    def test_health_connects_to_live_socket(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen()
            endpoint = 'http://127.0.0.1:%d/v1/systemone' % server.getsockname()[1]
            with patch.dict(os.environ, FLEXCELL_JEV_ENDPOINT=endpoint):
                self.assertTrue(ClefBackend().health()[0])

    def test_injected_transport_does_not_probe_network(self):
        with patch.dict(os.environ, FLEXCELL_JEV_ENDPOINT='http://127.0.0.1:1/v1/systemone'):
            self.assertTrue(ClefBackend(transport=lambda *a: {}).health()[0])

    def test_answers_wrapper_without_concentration_field(self):
        def transport(url, payload, timeout_s):
            return {'answers': {'next_action': {
                        'type': 'choice', 'choice': 'OBSERVE',
                        'probabilities': {'OBSERVE': 0.6, 'PICK': 0.3,
                                          'ABORT': 0.1}}}}

        resp = ClefBackend(transport=transport).classify(STATE, QUESTION)
        self.assertEqual(resp.choice, 'OBSERVE')
        self.assertAlmostEqual(resp.probability, 0.6)
        self.assertIsNone(resp.raw['model_sha256'])

    def test_unconfigured_endpoint_raises_runtime_error(self):
        saved = os.environ.pop('FLEXCELL_JEV_ENDPOINT', None)
        try:
            with self.assertRaises(RuntimeError):
                ClefBackend().classify(STATE, QUESTION)
            ok, detail = ClefBackend().health()
            self.assertFalse(ok)
            self.assertIn('FLEXCELL_JEV_ENDPOINT', detail)
        finally:
            if saved is not None:
                os.environ['FLEXCELL_JEV_ENDPOINT'] = saved

    def test_factory_wiring(self):
        self.assertIsInstance(make_backend('clef'), ClefBackend)
        with self.assertRaises(ValueError):
            make_backend('nope')


if __name__ == '__main__':
    unittest.main()
