"""Offline driver tests for the four-slot pick/place window.

Runs under `python3 -m unittest discover`, matching the team-handoff gate.
Covers result parsing, the single-run rule, the source-change scope,
unknown-terminal detection, window stop behaviour, the completion flag, and the
timeout cleanup that stops processes which escaped into their own session.
"""
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

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
    """The change check must cover what the slot actually executes or loads."""

    def test_execution_entry_is_hashed(self):
        self.assertIn('scripts/sim_smoke.py', rw.source_hashes())

    def test_configuration_is_hashed(self):
        hashes = rw.source_hashes()
        self.assertTrue(any(key.startswith('config/') for key in hashes))

    def test_world_scene_is_hashed(self):
        self.assertIn('worlds/flexcell_velocity_servo.sdf', rw.source_hashes())

    def test_runtime_dependencies_are_hashed(self):
        hashes = rw.source_hashes()
        self.assertTrue(any(key.startswith('infra/') for key in hashes))
        self.assertIn('setup/flexcell_admin.py', hashes)
        self.assertIn('plan_execute.py', hashes)

    def test_window_definition_is_hashed(self):
        self.assertIn('experiments/physical_capabilities/pick_place_reliability/preregistration.json',
                      rw.source_hashes())

    def test_world_change_changes_the_frozen_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'worlds').mkdir()
            world = root / 'worlds' / 'flexcell_velocity_servo.sdf'
            world.write_text('<world name="a"/>')
            previous = rw.ROOT
            rw.ROOT = root
            try:
                before = rw.source_hashes()
                world.write_text('<world name="b"/>')
                after = rw.source_hashes()
            finally:
                rw.ROOT = previous
            self.assertIn('worlds/flexcell_velocity_servo.sdf', before)
            self.assertNotEqual(before, after)


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
        self.assertEqual(payload['preregistration']['experiment'], 'unit-test')
        self.assertTrue((out / 'results.json').is_file())
        self.assertTrue((out / 'SHA256_MANIFEST.json').is_file())
        self.assertTrue((out / 'source_before.json').is_file())
        self.assertTrue((out / 'source_after.json').is_file())

    def test_empty_preregistration_is_rejected(self):
        with self.assertRaises(ValueError):
            rw.run_window(dict(self.prereg, slots=[]), self.root / 'out')


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

    def test_reap_stops_a_process_that_carries_the_marker(self):
        marker = 'reap-unit-%d' % os.getpid()
        env = dict(os.environ, FLEXCELL_WINDOW_SLOT_ID=marker)
        decoy = subprocess.Popen(
            [sys.executable, '-c', 'import time; time.sleep(60)'],
            env=env, start_new_session=True)
        try:
            deadline = time.monotonic() + 10
            while not rw.owned_pids(marker) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertIn(decoy.pid, rw.owned_pids(marker), 'marked process did not start')

            found, killed = rw.reap(marker, grace_s=1.0)

            self.assertEqual(found, 1)
            self.assertEqual(killed, 0)
            deadline = time.monotonic() + 10
            while decoy.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertIsNotNone(decoy.poll(), 'marked process survived reap')
            self.assertEqual(rw.reap(marker), (0, 0))
        finally:
            if decoy.poll() is None:
                decoy.kill()
                decoy.wait()

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


class InterruptCleanupTest(unittest.TestCase):
    """Ctrl+C and SIGTERM must clean the slot before the driver exits."""

    def _interrupt_case(self, sig, expected_code, expected_name):
        marker = 'unit-interrupt-%d-%s' % (os.getpid(), sig)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            driver = pathlib.Path(__file__).resolve().parents[1]
            helper = root / 'driver.py'
            helper.write_text(
                'import json, os, sys\n'
                'sys.path.insert(0, %r)\n' % str(driver) +
                'import run_window as rw\n'
                'marker = %r\n' % marker +
                'env = dict(os.environ, FLEXCELL_WINDOW_SLOT_ID=marker)\n'
                'with open(%r, "wb") as log:\n' % str(root / 'slot.log') +
                '    code, cleanup = rw.run_slot(\n'
                '        [sys.executable, "-c", "import time; time.sleep(60)"],\n'
                '        env, log, timeout_s=120, grace_s=2)\n'
                'print(json.dumps(dict(code=code, cleanup=cleanup)))\n')
            proc = subprocess.Popen([sys.executable, str(helper)], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 15
                while not rw.owned_pids(marker) and time.monotonic() < deadline:
                    time.sleep(0.1)
                self.assertTrue(rw.owned_pids(marker), 'slot child never started')

                os.kill(proc.pid, sig)
                out, err = proc.communicate(timeout=30)

                self.assertEqual(proc.returncode, 0, err)
                payload = json.loads(out.strip().splitlines()[-1])
                self.assertEqual(payload['code'], expected_code)
                self.assertEqual(payload['cleanup']['reason'], expected_name)
                self.assertEqual(payload['cleanup']['left'], 0)
                deadline = time.monotonic() + 10
                while rw.owned_pids(marker) and time.monotonic() < deadline:
                    time.sleep(0.1)
                self.assertEqual(rw.owned_pids(marker), [])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                for pid in rw.owned_pids(marker):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass

    def test_sigint_cleans_up_before_exit(self):
        self._interrupt_case(signal.SIGINT, 130, 'SIGINT')

    def test_sigterm_cleans_up_before_exit(self):
        self._interrupt_case(signal.SIGTERM, 143, 'SIGTERM')

    def test_sighup_cleans_up_before_exit(self):
        self._interrupt_case(signal.SIGHUP, 129, 'SIGHUP')


class InterruptedWindowTest(unittest.TestCase):
    def test_interrupted_slot_is_kept_and_partial_results_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            prereg = dict(
                slots=[dict(label='A', case='normal'), dict(label='B', case='normal')],
                slot_timeout_s=1, window_budget_s=1000,
                backend='velocity_servo', skill_backend='legacy',
                experiment='unit-test')
            cleanup = dict(graceful=True, survivors=0, killed=0, left=0, reason='SIGINT')
            with mock.patch.object(rw, 'run_slot', return_value=(130, cleanup)):
                payload = rw.run_window(prereg, root / 'out')

            self.assertEqual([r['status'] for r in payload['results']],
                             ['INTERRUPTED', 'NOT_RUN'])
            self.assertTrue(payload['interrupted'])
            self.assertEqual(payload['interrupt_signal'], 'SIGINT')
            self.assertFalse(payload['all_slots_completed'])
            self.assertTrue((root / 'out' / 'results.json').is_file())
            self.assertTrue((root / 'out' / 'results.partial.json').is_file())

    def test_signal_during_result_parsing_keeps_the_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            prereg = dict(
                slots=[dict(label='A', case='normal'), dict(label='B', case='normal')],
                slot_timeout_s=1, window_budget_s=1000,
                backend='velocity_servo', skill_backend='legacy',
                experiment='unit-test')

            def runner(label, case, slot_out, index):
                write_result(slot_out, 'normal')
                return 0

            real_one_result = rw.one_result

            def interrupt_then_parse(*args):
                os.kill(os.getpid(), signal.SIGINT)
                return real_one_result(*args)

            with mock.patch.object(rw, 'one_result', side_effect=interrupt_then_parse):
                payload = rw.run_window(prereg, root / 'out', runner=runner)

            self.assertEqual([r['status'] for r in payload['results']],
                             ['INTERRUPTED', 'NOT_RUN'])
            self.assertTrue(payload['interrupted'])
            self.assertEqual(payload['interrupt_signal'], 'SIGINT')
            self.assertFalse(payload['all_slots_completed'])


class ReapInterruptTest(unittest.TestCase):
    """A Ctrl+C during the post-slot reap must not erase the executed slot."""

    def test_sigint_during_reap_keeps_the_slot_as_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            prereg = dict(
                slots=[dict(label='A', case='normal'), dict(label='B', case='normal')],
                slot_timeout_s=5, window_budget_s=1000,
                backend='velocity_servo', skill_backend='legacy',
                experiment='unit-test')

            def fake_command(*_args, **_kwargs):
                return [sys.executable, '-c', 'pass']

            def fake_reap(marker, grace_s=10.0):
                os.kill(os.getpid(), signal.SIGINT)
                return 0, 0

            with mock.patch.object(rw, 'slot_command', fake_command), \
                    mock.patch.object(rw, 'reap', fake_reap):
                payload = rw.run_window(prereg, root / 'out')

            first, second = payload['results']
            self.assertEqual(first['status'], 'INTERRUPTED')
            self.assertIn('SIGINT', first['reason'])
            self.assertIn('during cleanup', first['reason'])
            self.assertEqual(second['status'], 'NOT_RUN')
            self.assertTrue(payload['interrupted'])
            self.assertEqual(payload['interrupt_signal'], 'SIGINT')
            self.assertFalse(payload['all_slots_completed'])


if __name__ == '__main__':
    unittest.main()
