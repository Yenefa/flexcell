#!/usr/bin/env python3
"""Tests for verify.py: a missing log MUST be caught, and a complete set MUST pass.

WHY THE TESTS MATTER MORE THAN THE CHECKER
    A missing-item checker has one job and one way to fail catastrophically: pass
    when something is absent. That is the same shape as the vacuous acceptance
    clause this repository has already been burned by, so the tests deliberately
    construct incomplete runs and assert a NON-ZERO exit. Every test builds its own
    throwaway fixture directory; nothing here touches real evidence.

    The tests also cover the case that motivated #231 in the first place: a log
    written to the shared default log_dir instead of the run directory. That run
    LOOKS complete if you only ask os.path.exists() on the run dir, and the data
    does exist - so a naive checker either misses it or, worse, a human finds the
    global file and assumes it belongs to the run in hand.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, 'verify.py')


def run_verify(*args):
    """Invoke verify.py as a subprocess, so the EXIT CODE is what is tested."""
    proc = subprocess.run([sys.executable, VERIFY] + list(args),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


class Fixture(object):
    """A throwaway run directory that looks like a real one."""

    def __init__(self, outcome='normal', logs=('move_to_pose.jsonl',
                                               'push.jsonl'),
                 artefact=True):
        self.root = tempfile.mkdtemp(prefix='issue231-')
        self.run = os.path.join(self.root, 'run', 't1')
        self.skills = os.path.join(self.run, 'sim', 'skills')
        os.makedirs(self.skills, exist_ok=True)
        for name in logs:
            with open(os.path.join(self.skills, name), 'w', encoding='utf-8') as fh:
                fh.write('{"event": "recorded"}\n')
        if artefact:
            with open(os.path.join(self.run, 'trial_record.json'), 'w',
                      encoding='utf-8') as fh:
                json.dump({'trial': 1}, fh)
        if outcome == 'failed':
            with open(os.path.join(self.run, 'invalid_infra.txt'), 'w',
                      encoding='utf-8') as fh:
                fh.write('INVALID_INFRA test fixture\n')
        elif outcome == 'startup':
            with open(os.path.join(self.run, 'startup_failure.json'), 'w',
                      encoding='utf-8') as fh:
                json.dump({'stage': 'launch'}, fh)

    def remove(self, name):
        os.remove(os.path.join(self.skills, name))

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class CompleteSetPasses(unittest.TestCase):
    """The one case that must be green: a genuinely complete run."""

    def test_complete_push_run_exits_zero(self):
        fx = Fixture()
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 0, 'a complete run must exit 0, got %d\n%s'
                             % (code, out))
            self.assertIn('COMPLETE', out)
        finally:
            fx.cleanup()

    def test_complete_run_with_manifest(self):
        fx = Fixture(logs=('move_to_pose.jsonl', 'push.jsonl', 'observe.jsonl'))
        try:
            logs_dir = os.path.join(fx.run, 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            with open(os.path.join(logs_dir, 'expected_logs.txt'), 'w',
                      encoding='utf-8') as fh:
                fh.write('move_to_pose.jsonl\npush.jsonl  # trailing comment\n')
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 0, out)
        finally:
            fx.cleanup()


class MissingLogIsCaught(unittest.TestCase):
    """THE core requirement of #231: absence must be loud and named."""

    def test_missing_push_jsonl_is_caught(self):
        fx = Fixture(logs=('move_to_pose.jsonl',))
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, 'a missing log MUST exit non-zero\n%s' % out)
            self.assertIn('push.jsonl', out, 'the missing item must be named')
            self.assertIn('INCOMPLETE', out)
            self.assertNotIn('RESULT: COMPLETE', out)
        finally:
            fx.cleanup()

    def test_missing_move_to_pose_is_caught(self):
        fx = Fixture(logs=('push.jsonl',))
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, out)
            self.assertIn('move_to_pose.jsonl', out)
        finally:
            fx.cleanup()

    def test_all_logs_missing_is_caught(self):
        fx = Fixture(logs=())
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, out)
            self.assertIn('move_to_pose.jsonl', out)
            self.assertIn('push.jsonl', out)
        finally:
            fx.cleanup()

    def test_zero_byte_log_is_not_a_pass(self):
        """A file that exists but recorded nothing is not evidence."""
        fx = Fixture()
        try:
            open(os.path.join(fx.skills, 'push.jsonl'), 'w').close()
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, 'an empty log must not count as present\n%s' % out)
            self.assertIn('EMPTY', out)
        finally:
            fx.cleanup()

    def test_explicit_required_list_overrides_profile(self):
        fx = Fixture(logs=('move_to_pose.jsonl', 'push.jsonl'))
        try:
            code, out = run_verify(fx.run, '--required',
                                   'move_to_pose.jsonl,not_written.jsonl')
            self.assertEqual(code, 1, out)
            self.assertIn('not_written.jsonl', out)
        finally:
            fx.cleanup()


class SharedLogDirDefect(unittest.TestCase):
    """The actual #231 mechanism: the log exists, but not for THIS run."""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix='issue231-home-')
        self.saved_home = os.environ.get('HOME')
        os.environ['HOME'] = self.home
        self.global_dir = os.path.join(self.home, '.ros', 'flexcell')
        os.makedirs(self.global_dir, exist_ok=True)

    def tearDown(self):
        if self.saved_home is None:
            os.environ.pop('HOME', None)
        else:
            os.environ['HOME'] = self.saved_home
        shutil.rmtree(self.home, ignore_errors=True)

    def test_log_in_shared_dir_is_reported_as_misfiled_not_present(self):
        fx = Fixture(logs=('move_to_pose.jsonl',))
        try:
            # the push log went to the global default log_dir, as it really does
            with open(os.path.join(self.global_dir, 'push.jsonl'), 'w',
                      encoding='utf-8') as fh:
                fh.write('{"request_id": "some-other-run"}\n')
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1,
                             'a log in the shared dir must NOT satisfy the run\n%s' % out)
            self.assertIn('MISFILED', out)
            self.assertIn('push.jsonl', out)
            self.assertIn(self.global_dir, out,
                          'the shared location must be named so it can be checked')
        finally:
            fx.cleanup()

    def test_stale_shared_file_is_not_called_misfiled(self):
        """A shared file older than the run cannot be the run's data.

        Regression test for a false attribution this tool actually made on real
        data: a Nov-10 run was reported MISFILED against an Oct-05 global file.
        """
        fx = Fixture(logs=('move_to_pose.jsonl',))
        try:
            shared = os.path.join(self.global_dir, 'push.jsonl')
            with open(shared, 'w', encoding='utf-8') as fh:
                fh.write('{"request_id": "ancient-run"}\n')
            # make the shared file clearly older than the run's own log
            long_ago = os.path.getmtime(
                os.path.join(fx.skills, 'move_to_pose.jsonl')) - 5000000
            os.utime(shared, (long_ago, long_ago))
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, out)
            self.assertIn('MISSING', out)
            self.assertNotIn('MISFILED', out,
                             'a file that predates the run must not be reported as '
                             'this run\'s misfiled log')
            self.assertIn('predates this run', out)
        finally:
            fx.cleanup()

    def test_newer_shared_file_is_flagged_but_hedged(self):
        """A newer shared file is a candidate, and the wording must not overclaim."""
        fx = Fixture(logs=('move_to_pose.jsonl',))
        try:
            shared = os.path.join(self.global_dir, 'push.jsonl')
            with open(shared, 'w', encoding='utf-8') as fh:
                fh.write('{"request_id": "mixed"}\n')
            later = os.path.getmtime(
                os.path.join(fx.skills, 'move_to_pose.jsonl')) + 60
            os.utime(shared, (later, later))
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, out)
            self.assertIn('MISFILED', out)
            self.assertIn('MAY contain', out)
        finally:
            fx.cleanup()

    def test_absent_everywhere_is_missing_not_misfiled(self):
        fx = Fixture(logs=('move_to_pose.jsonl',))
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, out)
            self.assertIn('MISSING', out)
            self.assertNotIn('MISFILED', out)
        finally:
            fx.cleanup()


class OutcomeCoverage(unittest.TestCase):
    """#231 asks for normal completion, execution failure and startup failure."""

    def test_execution_failure_with_partial_logs_passes(self):
        """A failed run with a failure marker legitimately has fewer logs."""
        fx = Fixture(outcome='failed', logs=('move_to_pose.jsonl',))
        try:
            code, out = run_verify(fx.run, '--required', 'move_to_pose.jsonl')
            self.assertEqual(code, 0, 'a marked failure with its log is complete '
                                      'for that required set\n%s' % out)
        finally:
            fx.cleanup()

    def test_execution_failure_still_requires_its_logs(self):
        """Being failed does not excuse a missing log that the run should have."""
        fx = Fixture(outcome='failed', logs=())
        try:
            code, out = run_verify(fx.run, '--required', 'move_to_pose.jsonl')
            self.assertEqual(code, 1, 'a failure marker must not waive the log '
                                      'requirement\n%s' % out)
            self.assertIn('move_to_pose.jsonl', out)
        finally:
            fx.cleanup()

    def test_startup_failure_is_reported_with_its_marker(self):
        fx = Fixture(outcome='startup', logs=(), artefact=False)
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertIn('startup', out)
            # the required skill logs really are absent, so it is still incomplete
            self.assertEqual(code, 1, out)
            self.assertIn('push.jsonl', out)
        finally:
            fx.cleanup()

    def test_unmarked_empty_run_is_caught(self):
        """No logs, no artefacts, no marker: must NOT pass."""
        fx = Fixture(logs=(), artefact=False)
        try:
            code, out = run_verify(fx.run, '--profile', 'push')
            self.assertEqual(code, 1, 'an unattributable run must not pass\n%s' % out)
            self.assertIn('UNMARKED', out)
        finally:
            fx.cleanup()

    def test_missing_run_directory_is_caught(self):
        code, out = run_verify('/nonexistent/run/dir', '--profile', 'push')
        self.assertEqual(code, 1, out)
        self.assertIn('run directory', out)


class ScanMode(unittest.TestCase):
    """Whole-tree scan, which is how this would be pointed at a batch."""

    def test_scan_finds_incomplete_run_among_complete_ones(self):
        good = Fixture()
        bad = Fixture(logs=('move_to_pose.jsonl',))
        try:
            root = os.path.dirname(os.path.dirname(good.run))
            # put both runs side by side under one root
            shared = tempfile.mkdtemp(prefix='issue231-scan-')
            try:
                shutil.copytree(os.path.join(root, 'run'),
                                os.path.join(shared, 'good'))
                shutil.copytree(os.path.join(os.path.dirname(
                    os.path.dirname(bad.run)), 'run'),
                    os.path.join(shared, 'bad'))
                code, out = run_verify('--scan', shared, '--profile', 'push')
                self.assertEqual(code, 1, 'a batch with one bad run must exit '
                                          'non-zero\n%s' % out)
                self.assertIn('FAIL', out)
                self.assertIn('1 of 2', out)
            finally:
                shutil.rmtree(shared, ignore_errors=True)
        finally:
            good.cleanup()
            bad.cleanup()

    def test_scan_all_complete_exits_zero(self):
        fx = Fixture()
        try:
            root = tempfile.mkdtemp(prefix='issue231-scan-ok-')
            try:
                shutil.copytree(os.path.join(os.path.dirname(
                    os.path.dirname(fx.run)), 'run'),
                    os.path.join(root, 'good'))
                code, out = run_verify('--scan', root, '--profile', 'push')
                self.assertEqual(code, 0, out)
                self.assertIn('0 of 1', out)
            finally:
                shutil.rmtree(root, ignore_errors=True)
        finally:
            fx.cleanup()


class JsonOutput(unittest.TestCase):
    def test_json_reports_missing_items(self):
        fx = Fixture(logs=('move_to_pose.jsonl',))
        try:
            code, out = run_verify(fx.run, '--profile', 'push', '--json')
            self.assertEqual(code, 1, out)
            payload = json.loads(out[out.index('{'):])
            self.assertFalse(payload['complete'])
            names = [f['item'] for f in payload['findings']]
            self.assertIn('push.jsonl', names)
        finally:
            fx.cleanup()


class VacuousScanIsCaught(unittest.TestCase):
    """A scan that checked nothing must not report success."""

    def test_scan_of_empty_tree_is_an_error_not_a_pass(self):
        root = tempfile.mkdtemp(prefix='issue231-empty-')
        try:
            code, out = run_verify('--scan', root, '--profile', 'push')
            self.assertEqual(code, 2, 'a scan that found no run has proven nothing '
                                      'and must not exit 0\n%s' % out)
            self.assertIn('nothing was checked', out)
            self.assertNotIn('0 of 0 run(s) incomplete', out)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class LegacyLayout(unittest.TestCase):
    """Older runs write <run>/skills, not <run>/sim/skills. Both must be checked."""

    def test_legacy_skills_dir_is_found(self):
        root = tempfile.mkdtemp(prefix='issue231-legacy-')
        try:
            run = os.path.join(root, 'run-abc')
            skills = os.path.join(run, 'skills')
            os.makedirs(skills)
            with open(os.path.join(skills, 'move_to_pose.jsonl'), 'w') as fh:
                fh.write('{"event": "recorded"}\n')
            with open(os.path.join(run, 'result.json'), 'w') as fh:
                json.dump({'ok': True}, fh)
            # complete for a required set of just move_to_pose
            code, out = run_verify(run, '--required', 'move_to_pose.jsonl')
            self.assertEqual(code, 0, 'a legacy-layout run with its log must pass\n%s' % out)
            # and it is genuinely found by the scan, not skipped as a non-run
            code2, out2 = run_verify('--scan', root, '--required', 'move_to_pose.jsonl')
            self.assertEqual(code2, 0, out2)
            self.assertIn('runs found: 1', out2,
                          'the legacy run must be FOUND by the scan, not skipped')
            self.assertIn('0 of 1', out2)
            # missing log in the legacy layout is still caught
            os.remove(os.path.join(skills, 'move_to_pose.jsonl'))
            code3, out3 = run_verify(run, '--required', 'move_to_pose.jsonl')
            self.assertEqual(code3, 1, 'a missing log in the legacy layout must be '
                                       'caught\n%s' % out3)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class UsageErrors(unittest.TestCase):
    def test_no_arguments_is_usage_error_not_pass(self):
        code, _ = run_verify()
        self.assertEqual(code, 2, 'a misused checker must never exit 0')

    def test_both_run_and_scan_is_usage_error(self):
        code, _ = run_verify('x', '--scan', 'y')
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
