"""Offline driver tests for the four-slot pick/place window.

Runs under `python3 -m unittest discover`, matching the team-handoff gate.
Covers result parsing, the single-run rule, the source-change scope,
unknown-terminal detection, window stop behaviour, the completion flag, and the
timeout cleanup that stops processes which escaped into their own session.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
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

    def test_run_directory_without_result_is_rejected(self):
        write_result(self.root / 'NORMAL_1', 'normal', run_name='run-good')
        (self.root / 'NORMAL_1' / 'run-empty').mkdir()
        with self.assertRaises(ValueError) as ctx:
            rw.one_result(self.root / 'NORMAL_1', 'normal')
        self.assertIn('exactly one run-* directory', str(ctx.exception))

    def test_single_run_directory_without_result_is_rejected(self):
        (self.root / 'NORMAL_1' / 'run-empty').mkdir(parents=True)
        with self.assertRaises(ValueError) as ctx:
            rw.one_result(self.root / 'NORMAL_1', 'normal')
        self.assertIn('unreadable result', str(ctx.exception))


class SourceScopeTest(unittest.TestCase):
    """The change check must cover what the slot actually executes."""

    def test_execution_entry_is_hashed(self):
        self.assertIn('scripts/sim_smoke.py', rw.source_hashes())

    def test_configuration_is_hashed(self):
        hashes = rw.source_hashes()
        self.assertTrue(any(key.startswith('config/') for key in hashes))


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


class CompletionTest(unittest.TestCase):
    """The completion flag must follow `classify`, not the raw PASS string."""

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

    def test_last_slot_unknown_is_not_a_completed_window(self):
        def runner(label, case, slot_out, index):
            if label == 'B':
                write_result(slot_out, 'normal', motion_terminal_known=False)
            else:
                write_result(slot_out, 'normal')
            return 0

        payload = rw.run_window(self.prereg, self.root / 'out', runner=runner)

        self.assertEqual([r['status'] for r in payload['results']], ['OK', 'UNKNOWN'])
        self.assertTrue(payload['results'][0]['task_completed'])
        self.assertFalse(payload['results'][1]['task_completed'])
        self.assertFalse(payload['all_slots_completed'])
        self.assertIsNotNone(payload['stop_reason'])

    def test_reported_pass_is_kept_separate_from_completion(self):
        def runner(label, case, slot_out, index):
            if label == 'B':
                write_result(slot_out, 'normal', motion_terminal_known=False)
            else:
                write_result(slot_out, 'normal')
            return 0

        payload = rw.run_window(self.prereg, self.root / 'out', runner=runner)
        last = payload['results'][1]

        self.assertTrue(last['task_reported_pass'])
        self.assertFalse(last['task_completed'])


class TimeoutCleanupTest(unittest.TestCase):
    """A slot must not leave processes behind when the outer timeout fires."""

    def test_process_that_escaped_into_its_own_session_is_stopped(self):
        marker = 'unit-slot-%d' % os.getpid()
        env = dict(os.environ, FLEXCELL_WINDOW_SLOT_ID=marker)
        decoy = subprocess.Popen(
            [sys.executable, '-c', 'import time; time.sleep(60)'],
            env=env, start_new_session=True)
        try:
            with tempfile.TemporaryFile() as log:
                code, cleanup = rw.run_slot(
                    [sys.executable, '-c', 'import time; time.sleep(60)'],
                    dict(env, ROS_DOMAIN_ID='99'), log,
                    timeout_s=0.5, grace_s=0.5)

            self.assertEqual(code, 124)
            self.assertGreaterEqual(cleanup['survivors'], 1)
            self.assertEqual(cleanup['left'], 0)

            deadline = time.monotonic() + 10
            while decoy.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertIsNotNone(decoy.poll(), 'escaped process survived cleanup')
        finally:
            if decoy.poll() is None:
                decoy.kill()
                decoy.wait()


if __name__ == '__main__':
    unittest.main()
