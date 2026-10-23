"""Synthetic loopback HTTP tests. These never use a real model or GPU."""
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('clef_smoke', HERE / 'run_clef_replay.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class RecordedInputSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.weights = self.work / 'synthetic-fixture.gguf'
        self.weights.write_bytes(b'SYNTHETIC HTTP CLIENT TEST - NOT MODEL WEIGHTS')
        self.weight_patch = patch.object(smoke, 'Q8_SHA', hashlib.sha256(self.weights.read_bytes()).hexdigest())
        self.weight_patch.start()
        self.addCleanup(self.weight_patch.stop)
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop('FLEXCELL_JEV_CALIBRATION', None)
        self.requests = []
        self.mode = 'ok'
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append(payload)
                criteria = payload['questions']['next_action']['criteria']
                choice = sorted(criteria)[0]
                reply = {
                    'answers': {'next_action': {
                        'choice': 'NOT_AN_ACTION' if owner.mode == 'oov' else choice,
                        'probabilities': {k: int(k == choice) for k in criteria},
                        'confidence': 1,
                    }},
                    'usage': {'input_tokens': 17, 'output_tokens': 0, 'total_tokens': 17},
                    'test_fixture': 'SYNTHETIC; NOT GPU EVIDENCE',
                }
                if owner.mode == 'missing_usage':
                    reply.pop('usage')
                elif owner.mode == 'wrong_shape':
                    reply = ['not a typed response']
                body = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        def stop():
            self.server.shutdown()
            self.server.server_close()
            thread.join()
        self.addCleanup(stop)

    def execute(self):
        out = self.work / 'report.json'
        argv = ['--weights', str(self.weights), '--model', 'synthetic-http-fixture',
                '--endpoint', f'http://127.0.0.1:{self.server.server_port}/v1/systemone',
                '--out', str(out)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = smoke.main(argv)
        return code, json.loads(out.read_text(encoding='utf-8'))

    def test_complete_http_smoke_keeps_gpu_identity_unverified(self):
        code, report = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'MODEL_API_PASS')
        self.assertEqual(len(self.requests), 20)
        self.assertEqual(report['summary']['tokens'], 340)
        self.assertEqual(report['gpu_execution'], 'REQUIRES_SERVER_LOG_EVIDENCE')
        self.assertEqual(report['served_weight_identity'], 'REQUIRES_SERVER_PROCESS_AND_LOG_CHECK')
        self.assertLess(report['summary']['recorded_action_agreements'], 20)
        self.assertTrue(all(row['pass'] for row in report['rows']))
        self.assertTrue(all(row['decision']['policy_trace']['source'] == 'jev' for row in report['rows']))

    def test_oov_fallback_fails_and_stops_after_one_call(self):
        self.mode = 'oov'
        code, report = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(report['rows'][0]['decision']['policy_trace']['fallback'])
        self.assertIn('NOT_AN_ACTION', report['rows'][0]['response_json'])

    def test_missing_usage_is_not_counted_as_valid_fast_evidence(self):
        self.mode = 'missing_usage'
        code, report = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(report['rows'][0]['pass'])
        self.assertIn('Missing positive measured token usage', report['rows'][0]['errors'])

    def test_malformed_response_preserves_failure_evidence(self):
        self.mode = 'wrong_shape'
        code, report = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(report['rows']), 1)
        self.assertIn('not a typed response', report['rows'][0]['response_json'])

    def test_weight_drift_sends_zero_requests(self):
        self.weights.write_bytes(b'CHANGED SYNTHETIC FIXTURE')
        code, report = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(len(self.requests), 0)
        self.assertEqual(report['model_calls_attempted'], 0)

    def test_existing_report_is_preserved_without_requests(self):
        out = self.work / 'report.json'
        out.write_text('{"original_evidence": true}\n')
        original = out.read_bytes()
        code, _ = self.execute()
        self.assertEqual(code, 2)
        self.assertEqual(out.read_bytes(), original)
        self.assertEqual(len(self.requests), 0)


if __name__ == '__main__':
    unittest.main()
