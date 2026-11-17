#!/usr/bin/env python3
"""Tests for scripts/accept_run.py.

WHY: this script is the last gate between a failed run and a claim of success.
Its failure modes are silent - a missing measurement read as a warning, or a
window directory resolved to the wrong run - so each required behaviour is
pinned to a fixture built from the real artifact shapes.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import accept_run  # noqa: E402  (the scripts directory is added above)

DEFAULT_VERIFY = 'measured within 0.060m of expected (err=0.0120)'
DEFAULT_PLACE = 'placed target_box_a: drop error 0.012m'


class AcceptRunTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def make_run(self, name='run-abc123', status='PASS',
                 outcome='OUTCOME_SUCCEEDED', error_code='ERR_NONE',
                 final_error=0.013, verify_detail=DEFAULT_VERIFY,
                 place_detail=DEFAULT_PLACE, result=True):
        run = self.root / name
        (run / 'skills').mkdir(parents=True, exist_ok=True)
        if result:
            task = {'outcome': outcome, 'error_code': error_code}
            if final_error is not None:
                task['final_position_error_m'] = final_error
            payload = {'status': status, 'task': task}
            (run / 'result.json').write_text(json.dumps(payload) + '\n',
                                             encoding='utf-8')
        if verify_detail is not None:
            (run / 'skills' / 'verify.jsonl').write_text(
                json.dumps({'detail': verify_detail}) + '\n', encoding='utf-8')
        if place_detail is not None:
            (run / 'skills' / 'place.jsonl').write_text(
                json.dumps({'detail': place_detail}) + '\n', encoding='utf-8')
        return run

    def test_pass_reports_metrics(self):
        run = self.make_run()
        report = accept_run.evaluate(run)
        self.assertTrue(report['pass'], report['reasons'])
        self.assertEqual(report['reasons'], [])
        self.assertEqual(report['warnings'], [])
        self.assertAlmostEqual(report['metrics']['final_error_mm'], 13.0)
        self.assertAlmostEqual(report['metrics']['verify_error_mm'], 12.0)
        self.assertAlmostEqual(report['metrics']['place_drop_mm'], 12.0)
        self.assertAlmostEqual(report['metrics']['place_verify_delta_mm'], 0.0)
        self.assertEqual(report['run_dir'], str(run.resolve()))

    def test_status_fail_is_rejected(self):
        run = self.make_run(status='ROBOT_FAILURE')
        report = accept_run.evaluate(run)
        self.assertFalse(report['pass'])
        self.assertEqual(len(report['reasons']), 1)
        self.assertIn('status', report['reasons'][0])

    def test_missing_verify_measurement_is_rejected(self):
        run = self.make_run(verify_detail=None)
        report = accept_run.evaluate(run)
        self.assertFalse(report['pass'])
        self.assertEqual(report['reasons'], ['no independent verify measurement'])
        self.assertIsNone(report['metrics']['verify_error_mm'])

    def test_place_verify_disagreement_is_rejected(self):
        run = self.make_run(
            verify_detail='measured within 0.060m of expected (err=0.0100)',
            place_detail='placed target_box_a: drop error 0.015m')
        report = accept_run.evaluate(run)
        self.assertFalse(report['pass'])
        self.assertEqual(report['reasons'], ['place/verify disagree'])
        self.assertAlmostEqual(report['metrics']['place_verify_delta_mm'], 5.0)

    def test_missing_result_json_is_rejected(self):
        run = self.make_run(result=False)
        report = accept_run.evaluate(run)
        self.assertFalse(report['pass'])
        self.assertIn('missing result.json', report['reasons'])

    def test_window_dir_with_one_run_is_resolved(self):
        run = self.make_run(name='run-abc123')
        report = accept_run.evaluate(self.root)
        self.assertTrue(report['pass'], report['reasons'])
        self.assertEqual(report['run_dir'], str(run.resolve()))

    def test_window_dir_with_two_runs_is_rejected(self):
        self.make_run(name='run-aaa111')
        self.make_run(name='run-bbb222')
        report = accept_run.evaluate(self.root)
        self.assertFalse(report['pass'])
        self.assertTrue(any('multiple run-*' in reason
                            for reason in report['reasons']),
                        report['reasons'])

    def test_dual_object_absence_of_final_error_is_a_warning(self):
        run = self.make_run(final_error=None)
        report = accept_run.evaluate(run)
        self.assertTrue(report['pass'], report['reasons'])
        self.assertEqual(report['reasons'], [])
        self.assertTrue(any('final_position_error_m' in warning
                            for warning in report['warnings']),
                        report['warnings'])
        self.assertIsNone(report['metrics']['final_error_mm'])

    def test_cli_line_json_and_exit_codes(self):
        good = self.make_run(name='run-good')
        bad = self.make_run(name='run-bad', status='ROBOT_FAILURE')
        missing = self.root / 'run-does-not-exist'
        json_out = self.root / 'report.json'

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(accept_run.main([str(good)]), 0)
            self.assertEqual(accept_run.main([str(bad)]), 1)
            self.assertEqual(accept_run.main([str(missing)]), 2)
            self.assertEqual(
                accept_run.main([str(good), '--json', str(json_out)]), 0)

        self.assertTrue(out.getvalue().startswith('ACCEPT PASS '), out.getvalue())
        written = json.loads(json_out.read_text(encoding='utf-8'))
        self.assertTrue(written['pass'])
        self.assertEqual(written['run_dir'], str(good.resolve()))


if __name__ == '__main__':
    unittest.main()
