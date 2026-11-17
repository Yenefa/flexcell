"""Pairing rules and landing join for the carry-offset aggregator."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import analyze_carry_offset as ac  # noqa: E402


def write_slot(root, label, engage=(0.0, 0.0, 0.0), release=(0.001, 0.0, 0.0),
               grasp=None, landing=0.008, samples=None, skips=0, run='run-test'):
    slot = pathlib.Path(root) / label
    run_dir = slot / run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'result.json').write_text(json.dumps(dict(
        case='normal', status='PASS',
        task=dict(outcome='OUTCOME_SUCCEEDED', final_position_error_m=landing))))
    if samples is None:
        rows = [
            dict(event='engage', object_in_tcp=list(engage) + [0, 0, 0, 1],
                 carry_session='s1', source='SIMULATION_GROUND_TRUTH', world_revision=1),
        ]
        if grasp is not None:
            rows.append(dict(event='grasp', object_in_tcp=list(grasp) + [0, 0, 0, 1],
                             carry_session='s1', source='SIMULATION_GROUND_TRUTH',
                             world_revision=2))
        rows += [
            dict(event='carry', object_in_tcp=list(release) + [0, 0, 0, 1],
                 carry_session='s1', source='SIMULATION_GROUND_TRUTH', world_revision=3),
            dict(event='release', object_in_tcp=list(release) + [0, 0, 0, 1],
                 carry_session='s1', source='SIMULATION_GROUND_TRUTH', world_revision=3),
        ]
    else:
        rows = samples
    (slot / 'carry_offset.jsonl').write_text(
        ''.join(json.dumps(r) + '\n' for r in rows))
    if skips:
        (slot / 'carry_offset_skips.jsonl').write_text(
            ''.join(json.dumps(dict(event='carry', reason='stale')) + '\n'
                    for _ in range(skips)))
    return slot


class PairTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pairs_engage_with_release_in_millimetres(self):
        write_slot(self.root, 'NORMAL_1', engage=(0.065, 0.0, -0.150),
                   release=(0.066, 0.001, -0.149), landing=0.0049)
        row = ac.slot_row(self.root, 'NORMAL_1')

        self.assertEqual(row['samples'], 3)
        self.assertAlmostEqual(row['engage_mm'][0], 65.0, places=6)
        self.assertAlmostEqual(row['release_mm'][2], -149.0, places=6)
        self.assertGreater(row['delta_norm_mm'], 0.0)
        self.assertAlmostEqual(row['landing_mm'], 4.9, places=6)

    def test_last_session_wins(self):
        write_slot(self.root, 'NORMAL_1', samples=[
            dict(event='engage', object_in_tcp=[0.1, 0, 0, 0, 0, 0, 1],
                 carry_session='old'),
            dict(event='release', object_in_tcp=[0.1, 0, 0, 0, 0, 0, 1],
                 carry_session='old'),
            dict(event='engage', object_in_tcp=[0.0, 0.0, 0.0, 0, 0, 0, 1],
                 carry_session='new'),
            dict(event='release', object_in_tcp=[0.002, 0, 0, 0, 0, 0, 1],
                 carry_session='new'),
        ])
        row = ac.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['session'], 'new')
        self.assertAlmostEqual(row['delta_norm_mm'], 2.0, places=6)

    def test_missing_probe_file_is_reported_not_zero(self):
        slot = write_slot(self.root, 'NORMAL_1')
        (slot / 'carry_offset.jsonl').unlink()
        row = ac.slot_row(self.root, 'NORMAL_1')
        self.assertEqual(row['samples'], 0)
        self.assertIsNone(row['engage_mm'])
        self.assertIsNone(row['delta_norm_mm'])
        self.assertEqual(row['landing_mm'], 8.0)

    def test_release_without_engage_is_not_paired(self):
        write_slot(self.root, 'NORMAL_1', samples=[
            dict(event='release', object_in_tcp=[0.001, 0, 0, 0, 0, 0, 1]),
        ])
        row = ac.slot_row(self.root, 'NORMAL_1')
        self.assertIsNone(row['delta_norm_mm'])
        self.assertIsNone(row['engage_mm'])

    def test_settled_sample_comes_from_the_first_revision_change(self):
        # engage is taken while the gripper closes; the first new revision is the
        # held pose, so lift and slip are reported separately
        write_slot(self.root, 'NORMAL_1',
                   engage=(0.010, 0.0, -0.030),
                   grasp=(0.001, 0.0, 0.0),
                   release=(0.002, 0.0, 0.0))
        row = ac.slot_row(self.root, 'NORMAL_1')
        session = row['sessions'][0]

        self.assertEqual(session['settled_event'], 'grasp')
        self.assertAlmostEqual(session['lift_mm'], 31.32, places=1)
        self.assertAlmostEqual(session['slip_mm'], 1.0, places=6)

    def test_dual_object_keeps_both_sessions(self):
        write_slot(self.root, 'DUAL_1', samples=[
            dict(event='engage', object_in_tcp=[0.010, 0, 0, 0, 0, 0, 1],
                 carry_session='target_box_a', object='target_box_a'),
            dict(event='release', object_in_tcp=[0.011, 0, 0, 0, 0, 0, 1],
                 carry_session='target_box_a', object='target_box_a'),
            dict(event='engage', object_in_tcp=[0.000, 0, 0, 0, 0, 0, 1],
                 carry_session='target_box_b', object='target_box_b'),
            dict(event='release', object_in_tcp=[0.002, 0, 0, 0, 0, 0, 1],
                 carry_session='target_box_b', object='target_box_b'),
        ])
        row = ac.slot_row(self.root, 'DUAL_1')

        self.assertEqual([s['object'] for s in row['sessions']],
                         ['target_box_a', 'target_box_b'])
        self.assertEqual(row['sessions_paired'], 2)
        self.assertEqual(row['object'], 'target_box_b')  # last paired session
        self.assertAlmostEqual(row['delta_norm_mm'], 2.0, places=6)
        self.assertEqual(ac.summarize([row])['sessions_total'], 2)


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_and_ranges(self):
        write_slot(self.root, 'NORMAL_1', engage=(0, 0, 0), release=(0.001, 0, 0))
        write_slot(self.root, 'NORMAL_2', engage=(0, 0, 0), release=(0.003, 0, 0))
        rows = [ac.slot_row(self.root, label)
                for label in ('NORMAL_1', 'NORMAL_2', 'DUAL_1', 'DUAL_2')]
        summary = ac.summarize(rows)

        self.assertEqual(summary['slots_attempted'], 4)
        self.assertEqual(summary['slots_with_probe'], 2)
        self.assertEqual(summary['slots_paired'], 2)
        self.assertEqual(summary['slots_missing'], 2)
        self.assertAlmostEqual(summary['delta_norm_mm']['min'], 1.0, places=6)
        self.assertAlmostEqual(summary['delta_norm_mm']['max'], 3.0, places=6)
        self.assertEqual(summary['landing_mm']['n'], 2)

    def test_cli_exits_nonzero_without_pairs(self):
        write_slot(self.root, 'NORMAL_1')
        for label in ('NORMAL_1',):
            (self.root / label / 'carry_offset.jsonl').unlink()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            code = ac.main([str(self.root)])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
