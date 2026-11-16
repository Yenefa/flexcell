"""Tests for the artifact-only window aggregator (no ROS, no simulator)."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import analyze_windows as aw  # noqa: E402


def make_slot(root, label, error_m, place_detail, verify_detail, targets):
    run = pathlib.Path(root) / label / 'run-test'
    (run / 'skills').mkdir(parents=True)
    (run / 'result.json').write_text(json.dumps({
        'case': 'normal', 'status': 'PASS',
        'task': dict(outcome='OUTCOME_SUCCEEDED', error_code='ERR_NONE',
                     wall_seconds=14.0, final_position_error_m=error_m),
    }))
    (run / 'skills/place.jsonl').write_text(json.dumps({'detail': place_detail}) + '\n')
    (run / 'skills/verify.jsonl').write_text(json.dumps({'detail': verify_detail}) + '\n')
    (run / 'skills/move_to_pose.jsonl').write_text(
        ''.join(json.dumps({'target': {'position': list(t)}}) + '\n' for t in targets))


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
        self.assertEqual(row['final_error_mm'], 7.6)
        self.assertEqual(row['place_drop_mm'], 8.0)
        self.assertEqual(row['verify_error_mm'], 7.6)
        self.assertEqual(row['last_targets'][0], (0.12, -0.15, 0.1895))

    def test_missing_slot_is_reported(self):
        self.assertTrue(aw.slot_row(self.root, 'NORMAL_1')['missing'])


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


if __name__ == '__main__':
    unittest.main()
