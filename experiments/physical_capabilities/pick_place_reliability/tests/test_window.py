"""Offline driver tests for the four-slot pick/place window.

Runs under `python3 -m unittest discover`, matching the team-handoff gate.
Covers the seven declared cases: success, task failure, nested directory,
multiple results, missing file, outer timeout, unknown terminal state.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import run_window as rw  # noqa: E402


def write_result(directory, case='normal', status='PASS', run_name='run-test', **extra):
    run = pathlib.Path(directory) / run_name
    run.mkdir(parents=True, exist_ok=True)
    payload = dict(case=case, status=status,
                   task=dict(outcome='OUTCOME_SUCCEEDED', error_code='ERR_NONE'),
                   **extra)
    path = run / 'result.json'
    path.write_text(json.dumps(payload))
    return path


class OneResultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_is_ok(self):
        write_result(self.root / 'NORMAL_1', 'normal')
        result, _ = rw.one_result(self.root / 'NORMAL_1', 'normal')
        self.assertEqual(rw.classify(result, 0), 'OK')

    def test_task_failure_is_not_ok(self):
        write_result(self.root / 'NORMAL_1', 'normal', status='ROBOT_FAILURE')
        result, _ = rw.one_result(self.root / 'NORMAL_1', 'normal')
        self.assertEqual(rw.classify(result, 0), 'TASK_FAILED')

    def test_nested_directory_is_rejected(self):
        nested = self.root / 'NORMAL_1' / 'run-test' / 'sub'
        nested.mkdir(parents=True)
        (nested / 'result.json').write_text(json.dumps(dict(case='normal', status='PASS')))
        with self.assertRaises(ValueError):
            rw.one_result(self.root / 'NORMAL_1', 'normal')

    def test_multiple_results_are_rejected(self):
        write_result(self.root / 'NORMAL_1', 'normal', run_name='run-first')
        write_result(self.root / 'NORMAL_1', 'normal', run_name='run-second')
        with self.assertRaises(ValueError):
            rw.one_result(self.root / 'NORMAL_1', 'normal')

    def test_missing_file_is_rejected(self):
        (self.root / 'NORMAL_1').mkdir()
        with self.assertRaises(ValueError):
            rw.one_result(self.root / 'NORMAL_1', 'normal')

    def test_case_mismatch_is_rejected(self):
        write_result(self.root / 'NORMAL_1', 'dual_object')
        with self.assertRaises(ValueError):
            rw.one_result(self.root / 'NORMAL_1', 'normal')


class UnknownTest(unittest.TestCase):
    def test_unknown_markers(self):
        payloads = [
            dict(status='STATE_UNKNOWN'),
            dict(status='ACTION_TERMINAL_UNKNOWN'),
            dict(motion_terminal_known=False),
            dict(terminal_known=False),
            dict(error_code=33),
            dict(nested=dict(error_code=33)),
            dict(nested=[dict(terminal_known=False)]),
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertTrue(rw.unknown(payload))

    def test_clean_result_is_known(self):
        self.assertFalse(rw.unknown(dict(status='PASS', error_code='ERR_NONE')))


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.prereg = dict(
            slots=[dict(label='A', case='normal'), dict(label='B', case='normal')],
            slot_timeout_s=1, window_budget_s=1000,
            backend='velocity_servo', skill_backend='legacy',
            experiment='unit-test')

    def tearDown(self):
        self.tmp.cleanup()

    def test_outer_timeout_stops_following_slots(self):
        def runner(label, case, slot_out, index):
            pathlib.Path(slot_out).mkdir(parents=True, exist_ok=True)
            return 124

        payload = rw.run_window(self.prereg, self.root / 'out', runner=runner)
        self.assertEqual(payload['results'][0]['status'], 'UNKNOWN')
        self.assertEqual(payload['results'][1]['status'], 'NOT_RUN')
        self.assertFalse(payload['all_slots_completed'])

    def test_unknown_terminal_stops_following_slots(self):
        def runner(label, case, slot_out, index):
            pathlib.Path(slot_out).mkdir(parents=True, exist_ok=True)
            if label == 'A':
                write_result(slot_out, 'normal', status='STATE_UNKNOWN')
            return 0

        payload = rw.run_window(self.prereg, self.root / 'out', runner=runner)
        self.assertEqual(payload['results'][0]['status'], 'UNKNOWN')
        self.assertEqual(payload['results'][1]['status'], 'NOT_RUN')

    def test_success_writes_results_and_manifest(self):
        def runner(label, case, slot_out, index):
            write_result(slot_out, 'normal')
            return 0

        payload = rw.run_window(self.prereg, self.root / 'out', runner=runner)
        out = self.root / 'out'
        self.assertTrue(payload['all_slots_completed'])
        self.assertTrue((out / 'results.json').is_file())
        self.assertTrue((out / 'SHA256_MANIFEST.json').is_file())


if __name__ == '__main__':
    unittest.main()
