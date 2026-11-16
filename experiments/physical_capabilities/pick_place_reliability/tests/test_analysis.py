"""Tests for the artifact-only window aggregator (no ROS, no simulator)."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import analyze_windows as aw  # noqa: E402


def write_driver_row(root, label, status='OK', exit_code=None):
    """Record the window driver's verdict, as run_window does in results.json."""
    path = pathlib.Path(root) / 'results.json'
    data = json.loads(path.read_text()) if path.exists() else {'results': []}
    rows = [r for r in data.get('results', []) if r.get('label') != label]
    rows.append(dict(label=label, status=status,
                     driver_exit=(0 if status == 'OK' else 1)
                     if exit_code is None else exit_code))
    data['results'] = rows
    path.write_text(json.dumps(data))


def make_slot(root, label, error_m, place_detail, verify_detail, targets,
              run_name='run-test', status='PASS', outcome='OUTCOME_SUCCEEDED',
              driver_status='OK'):
    run = pathlib.Path(root) / label / run_name
    (run / 'skills').mkdir(parents=True, exist_ok=True)
    (run / 'result.json').write_text(json.dumps({
        'case': 'normal', 'status': status,
        'task': dict(outcome=outcome, error_code='ERR_NONE',
                     wall_seconds=14.0, final_position_error_m=error_m),
    }))
    if place_detail is not None:
        (run / 'skills/place.jsonl').write_text(json.dumps({'detail': place_detail}) + '\n')
    if verify_detail is not None:
        (run / 'skills/verify.jsonl').write_text(json.dumps({'detail': verify_detail}) + '\n')
    (run / 'skills/move_to_pose.jsonl').write_text(
        ''.join(json.dumps({'target': {'position': list(t)}}) + '\n' for t in targets))
    write_driver_row(root, label, driver_status)


class ParseTest(unittest.TestCase):
    def test_metres_become_millimetres(self):
        self.assertEqual(aw.parse_mm('placed target_box_a: drop error 0.008m', 'drop error'), 8.0)
        self.assertEqual(aw.parse_mm('measured within 0.060m of expected (err=0.0001)', 'err='), 0.1)

    def test_missing_marker_is_none(self):
        self.assertIsNone(aw.parse_mm('no measurement here', 'drop error'))
        self.assertIsNone(aw.parse_mm(None, 'err='))


class SlotRowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_declared_fields(self):
        make_slot(self.root, 'NORMAL_1', 0.0076,
                  'placed target_box_a: drop error 0.008m',
                  'measured within 0.060m of expected (err=0.0076)',
                  [(0.12, -0.15, 0.1895), (0.12, -0.15, 0.2895)])
        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'OK')
        self.assertEqual(row['final_error_mm'], 7.6)
        self.assertEqual(row['place_drop_mm'], 8.0)
        self.assertEqual(row['verify_error_mm'], 7.6)
        self.assertEqual(row['last_targets'][0], (0.12, -0.15, 0.1895))

    def test_missing_slot_is_reported(self):
        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'MISSING')
        self.assertTrue(row['reason'])


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_completed_slots_and_spread(self):
        make_slot(self.root, 'NORMAL_1', 0.0076, 'drop error 0.008m', 'err=0.0076',
                  [(0.12, -0.15, 0.1895)])
        make_slot(self.root, 'NORMAL_2', 0.0139, 'drop error 0.014m', 'err=0.0139',
                  [(0.12, -0.15, 0.1895)])
        rows = [aw.slot_row(self.root, label) for label in ('NORMAL_1', 'NORMAL_2')]
        summary = aw.summarize(rows)
        self.assertEqual(summary['slots_completed'], 2)
        self.assertEqual(summary['error_mm']['min'], 7.6)
        self.assertEqual(summary['error_mm']['max'], 13.9)
        self.assertEqual(summary['unique_release_target_sets'], 1)
        self.assertLess(summary['max_place_verify_delta_mm'], 1.0)

    def test_detects_two_distinct_target_sets(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        make_slot(self.root, 'NORMAL_2', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.13, -0.15, 0.1895)])
        rows = [aw.slot_row(self.root, label) for label in ('NORMAL_1', 'NORMAL_2')]
        self.assertEqual(aw.summarize(rows)['unique_release_target_sets'], 2)


class ValidityTest(unittest.TestCase):
    """A failed or ambiguous slot must never become a zero-error sample."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_slot_with_default_zero_error_is_not_counted(self):
        run = self.root / 'NORMAL_1' / 'run-x'
        run.mkdir(parents=True)
        (run / 'result.json').write_text(json.dumps({
            'case': 'normal', 'status': 'ROBOT_FAILURE',
            'task': dict(outcome='OUTCOME_FAILED', error_code='ERR_ROBOT_FAILED',
                         final_position_error_m=0.0),
        }))
        write_driver_row(self.root, 'NORMAL_1', 'TASK_FAILED')

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'TASK_FAILED')

        summary = aw.summarize([row])
        self.assertEqual(summary['slots_completed'], 0)
        self.assertEqual(summary['slots_task_failed'], 1)
        self.assertIsNone(summary['error_mm']['mean'])
        self.assertIsNone(summary['max_place_verify_delta_mm'])
        self.assertEqual(summary['excluded'][0]['status'], 'TASK_FAILED')

    def test_unknown_slot_is_not_counted(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        path = self.root / 'NORMAL_1' / 'run-test' / 'result.json'
        payload = json.loads(path.read_text())
        payload['motion_terminal_known'] = False
        path.write_text(json.dumps(payload))

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(aw.summarize([row])['slots_completed'], 0)

    def test_two_run_directories_are_ambiguous_not_the_first(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)], run_name='run-a')
        make_slot(self.root, 'NORMAL_1', 0.009, 'drop error 0.009m', 'err=0.009',
                  [(0.12, -0.15, 0.1895)], run_name='run-b')

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'AMBIGUOUS')
        self.assertIn('2 run-* directories', row['reason'])
        self.assertEqual(aw.summarize([row])['slots_completed'], 0)

    def test_run_directory_without_result_is_not_silently_skipped(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        (self.root / 'NORMAL_1' / 'run-empty').mkdir()

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'AMBIGUOUS')

    def test_missing_verify_measurement_stays_unknown(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', None,
                  [(0.12, -0.15, 0.1895)])

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'OK')
        self.assertIsNone(row['verify_error_mm'])

        summary = aw.summarize([row])
        self.assertEqual(summary['slots_completed'], 1)
        self.assertIsNone(summary['max_place_verify_delta_mm'])
        self.assertEqual(summary['place_verify_delta_mm']['n'], 0)

    def test_missing_final_error_is_unmeasured_not_zero(self):
        make_slot(self.root, 'NORMAL_1', None, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'OK')
        self.assertIsNone(row['final_error_mm'])

        summary = aw.summarize([row])
        self.assertEqual(summary['slots_completed'], 0)
        self.assertEqual(summary['slots_unmeasured'], 1)
        self.assertEqual(summary['excluded'][0]['reason'], 'no final_position_error_m')


class DriverVerdictTest(unittest.TestCase):
    """The analyzer must not overrule the window driver's stop decision."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_driver_unknown_overrides_a_raw_pass(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        write_driver_row(self.root, 'NORMAL_1', 'UNKNOWN', exit_code=124)

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertIn('window driver status', row['reason'])

        summary = aw.summarize([row])
        self.assertEqual(summary['slots_completed'], 0)
        self.assertEqual(summary['slots_unknown'], 1)

    def test_unreadable_window_metadata_keeps_the_slot_unknown(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        (self.root / 'results.json').write_text('{"results": [')

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertIn('results.json', row['reason'])

        summary = aw.summarize([row])
        self.assertEqual(summary['slots_completed'], 0)
        self.assertEqual(summary['slots_metadata_missing'], 1)

    def test_missing_window_metadata_keeps_the_slot_unknown(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        (self.root / 'results.json').unlink()

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(aw.summarize([row])['slots_completed'], 0)

    def test_driver_ok_with_nonzero_exit_is_not_trusted(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        path = self.root / 'results.json'
        data = json.loads(path.read_text())
        data['results'][0]['driver_exit'] = 124
        path.write_text(json.dumps(data))

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertIn('driver_exit', row['reason'])
        self.assertEqual(aw.summarize([row])['slots_completed'], 0)

    def test_duplicate_driver_rows_keep_the_window_unknown(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        path = self.root / 'results.json'
        data = json.loads(path.read_text())
        data['results'].append(dict(data['results'][0]))
        path.write_text(json.dumps(data))

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertIn('duplicate', row['reason'])
        self.assertEqual(aw.summarize([row])['slots_completed'], 0)


class NonFiniteValueTest(unittest.TestCase):
    """NaN/Inf must not become a sample, a target or a zero-error measurement."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_non_finite_final_error_is_unmeasured(self):
        make_slot(self.root, 'NORMAL_1', float('nan'), 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'OK')
        self.assertIsNone(row['final_error_mm'])

        summary = aw.summarize([row])
        self.assertEqual(summary['slots_completed'], 0)
        self.assertEqual(summary['slots_unmeasured'], 1)
        self.assertIsNone(summary['error_mm']['mean'])

    def test_non_finite_target_is_rejected(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        (self.root / 'NORMAL_1/run-test/skills/move_to_pose.jsonl').write_text(
            json.dumps({'target': {'position': [0.12, float('nan'), 0.1895]}}) + '\n')

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'OK')
        self.assertEqual(row['last_targets'], [])
        self.assertTrue(any('non-finite target' in error['error']
                            for error in row['log_errors']))


class CorruptLogTest(unittest.TestCase):
    """A truncated JSONL line belongs to one slot, not to the whole report."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_truncated_line_is_recorded_and_other_slots_still_analyze(self):
        make_slot(self.root, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        make_slot(self.root, 'NORMAL_2', 0.014, 'drop error 0.014m', 'err=0.014',
                  [(0.12, -0.15, 0.1895)])
        with (self.root / 'NORMAL_1/run-test/skills/place.jsonl').open('a') as handle:
            handle.write('{"detail":\n')

        rows = [aw.slot_row(self.root, label) for label in ('NORMAL_1', 'NORMAL_2')]
        self.assertEqual(rows[0]['status'], 'OK')
        self.assertIsNone(rows[0]['place_drop_mm'])
        self.assertEqual(rows[0]['log_errors'][0]['file'], 'place.jsonl')
        self.assertIn('invalid JSON', rows[0]['log_errors'][0]['error'])
        self.assertEqual(rows[1]['place_drop_mm'], 14.0)

        summary = aw.summarize(rows)
        self.assertEqual(summary['slots_completed'], 2)
        self.assertEqual(summary['place_verify_delta_mm']['n'], 1)
        self.assertEqual(summary['max_place_verify_delta_mm'], 0.0)

    def test_non_object_line_is_recorded(self):
        make_slot(self.root, 'NORMAL_1', 0.008, None, 'err=0.008',
                  [(0.12, -0.15, 0.1895)])
        (self.root / 'NORMAL_1/run-test/skills/move_to_pose.jsonl').write_text('[1, 2, 3]\n')

        row = aw.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['status'], 'OK')
        self.assertEqual(row['last_targets'], [])
        self.assertTrue(any('not a JSON object' in e['error']
                            for e in row['log_errors']))


if __name__ == '__main__':
    unittest.main()
