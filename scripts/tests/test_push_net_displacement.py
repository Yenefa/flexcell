"""Cases for the read-only push progress / net displacement checker."""
import hashlib
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'push_net_displacement', Path(__file__).parents[1] / 'push_net_displacement.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

FORWARD = (-1.0, 0.0)


def pose(x, y, z=0.0175):
    return ('geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x={0}, y={1}, z={2}), '
            'orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))').format(x, y, z)


def report(before=None, after=None, along=None, cos=None, **extra):
    payload = dict(displacement_along_direction_m=along, requested_distance_m=0.09)
    if cos is not None:
        payload['direction_cos'] = cos
    elif along is not None and math.isfinite(float(along)) and float(along) != 0.0:
        payload['direction_cos'] = 0.999 if float(along) > 0 else -0.999
    if before is not None:
        payload['measured_before'] = pose(*before)
    if after is not None:
        payload['measured_after'] = pose(*after)
    payload.update(extra)
    return payload


class AuditTest(unittest.TestCase):
    def audit(self, payloads, direction=FORWARD):
        reports = [(Path('push_%02d.json' % index), payload)
                   for index, payload in enumerate(payloads)]
        return module.audit(reports, direction)

    def test_forward_progress_matches_net_displacement(self):
        result = self.audit([
            report((0.22, 0.0), (0.20, 0.0), 0.02),
            report((0.20, 0.0), (0.16, 0.0), 0.04),
        ])
        self.assertAlmostEqual(result['progress']['value_m'], 0.06)
        self.assertAlmostEqual(result['net']['value_m'], 0.06)
        self.assertAlmostEqual(result['difference']['value_m'], 0.0)
        self.assertEqual(result['net']['status'], module.KNOWN)

    def test_reverse_motion_is_signed_negative(self):
        result = self.audit([report((0.16, 0.0), (0.22, 0.0), -0.06)])
        self.assertAlmostEqual(result['net']['value_m'], -0.06)

    def test_lateral_motion_keeps_net_at_zero(self):
        result = self.audit([report((0.20, 0.0), (0.20, 0.05), 0.0)])
        self.assertAlmostEqual(result['net']['value_m'], 0.0)
        self.assertAlmostEqual(result['net']['lateral_m'], 0.05)
        self.assertAlmostEqual(result['net']['magnitude_m'], 0.05)

    def test_static_object_reports_zero(self):
        result = self.audit([report((0.22, 0.0), (0.22, 0.0), 0.0)])
        self.assertAlmostEqual(result['net']['value_m'], 0.0)
        self.assertAlmostEqual(result['difference']['value_m'], 0.0)

    def test_arbitrary_plane_direction_is_normalised(self):
        direction = module.plane_direction([0.6, 0.8])
        self.assertAlmostEqual(math.hypot(*direction), 1.0)
        result = self.audit([report((0.0, 0.0), (0.3, 0.4), 0.5)], direction)
        self.assertAlmostEqual(result['net']['value_m'], 0.5)
        self.assertAlmostEqual(result['net']['lateral_m'], 0.0)

    def test_missing_endpoints_yield_unknown_not_zero(self):
        result = self.audit([report(after=(0.16, 0.0), along=0.06)])
        self.assertEqual(result['net']['status'], module.UNKNOWN)
        self.assertIsNone(result['net']['value_m'])
        self.assertEqual(result['progress']['status'], module.KNOWN)
        self.assertEqual(result['difference']['status'], module.UNKNOWN)
        self.assertTrue(result['net']['reasons'])
        self.assertIn('net displacement is unknown', result['difference']['reasons'])

    def test_unknown_progress_keeps_the_net_measurement(self):
        result = self.audit([report((0.22, 0.0), (0.20, 0.0), float('nan')),
                             report((0.20, 0.0), (0.16, 0.0), 0.04)])
        self.assertEqual(result['progress']['status'], module.UNKNOWN)
        self.assertEqual(result['net']['status'], module.KNOWN)
        self.assertAlmostEqual(result['net']['value_m'], 0.06)
        self.assertEqual(result['difference']['status'], module.UNKNOWN)

    def test_mixed_requested_directions_refuse_to_sum(self):
        # A recovery attempt that was requested the other way round, as in the
        # archived same-condition batch: +0.0228 m then -0.0262 m.
        result = self.audit([report((0.22, 0.0), (0.20, 0.0), 0.0228),
                             report((0.20, 0.0), (0.17, 0.0), -0.0262)])
        self.assertEqual(result['progress']['status'], module.UNKNOWN)
        self.assertEqual(result['progress']['requested_directions'], module.UNKNOWN)
        self.assertIn('attempts were requested along different directions; their sum is not a displacement',
                      result['progress']['reasons'])
        self.assertIsNone(result['progress']['value_m'])

    def test_single_attempt_needs_no_direction_cosine(self):
        result = self.audit([report(along=0.03)])
        self.assertEqual(result['progress']['status'], module.KNOWN)
        self.assertAlmostEqual(result['progress']['value_m'], 0.03)

    def test_infinite_measurement_is_not_a_measurement(self):
        result = self.audit([report((0.22, 0.0), (0.20, 0.0), float('inf'))])
        self.assertEqual(result['progress']['status'], module.UNKNOWN)

    def test_overlapping_windows_show_up_as_a_difference(self):
        # Second action re-reports motion the first action already covered.
        result = self.audit([report((0.22, 0.0), (0.18, 0.0), 0.04),
                             report((0.18, 0.0), (0.12, 0.0), 0.10)])
        self.assertAlmostEqual(result['progress']['value_m'], 0.14)
        self.assertAlmostEqual(result['net']['value_m'], 0.10)
        self.assertAlmostEqual(result['difference']['value_m'], -0.04)

    def test_zero_direction_is_rejected(self):
        for bad in ([0.0, 0.0], [float('nan'), 1.0], [1.0]):
            with self.assertRaises(ValueError):
                module.plane_direction(bad)

    def test_no_verdict_is_emitted(self):
        result = self.audit([report((0.22, 0.0), (0.16, 0.0), 0.06)])
        self.assertEqual(result['task_outcome'], module.NOT_A_VERDICT)

    def test_unreadable_report_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'push_00.json'
            path.write_text('{not json')
            with self.assertRaises(ValueError):
                module.load_reports([path])


class TaskDirectionTest(unittest.TestCase):
    def task(self, goals):
        return dict(expected_goal=dict(push=goals))

    def test_single_goal_needs_no_object(self):
        name, direction = module.task_direction(self.task({'target_box_a': {'direction': [-1.0, 0.0]}}))
        self.assertEqual(name, 'target_box_a')
        self.assertEqual(direction, (-1.0, 0.0))

    def test_several_goals_require_an_explicit_object(self):
        goals = {'a': {'direction': [-1.0, 0.0]}, 'b': {'direction': [1.0, 0.0]}}
        with self.assertRaises(ValueError):
            module.task_direction(self.task(goals))
        self.assertEqual(module.task_direction(self.task(goals), 'b')[1], (1.0, 0.0))

    def test_unknown_object_is_rejected(self):
        with self.assertRaises(ValueError):
            module.task_direction(self.task({'a': {'direction': [-1.0, 0.0]}}), 'zzz')

    def test_missing_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            module.task_direction(self.task({'a': {}}))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run_dir = self.root / 'run'
        (self.run_dir / 'trial').mkdir(parents=True)
        self.task = self.root / 'task.json'
        self.task.write_text(json.dumps(dict(
            task_id='T08-push-test',
            expected_goal=dict(push=dict(target_box_a=dict(direction=[-1.0, 0.0]))))))
        self.payloads = [report((0.22, 0.0), (0.20, 0.0), 0.02),
                         report((0.20, 0.0), (0.16, 0.0), 0.04)]
        for index, payload in enumerate(self.payloads):
            (self.run_dir / 'trial' / ('push_%02d.json' % index)).write_text(json.dumps(payload))

    def test_writes_into_a_new_directory_and_leaves_the_run_untouched(self):
        before = [(path.name, hashlib.sha256(path.read_bytes()).hexdigest())
                  for path in sorted(self.run_dir.rglob('*.json'))]
        out = self.root / 'diagnostics'
        self.assertEqual(module.main(['--task', str(self.task), '--run-dir', str(self.run_dir),
                                      '--out', str(out)]), 0)
        result = json.loads((out / 'push_net_displacement.json').read_text())
        self.assertAlmostEqual(result['difference']['value_m'], 0.0)
        self.assertEqual(result['task_outcome'], module.NOT_A_VERDICT)
        self.assertTrue((out / 'push_net_displacement.md').is_file())
        after = [(path.name, hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(self.run_dir.rglob('*.json'))]
        self.assertEqual(before, after)
        self.assertTrue(result['inputs']['digests'])

    def test_refuses_to_write_inside_the_run(self):
        out = self.run_dir / 'diagnostics'
        self.assertEqual(module.main(['--task', str(self.task), '--run-dir', str(self.run_dir),
                                      '--out', str(out)]), 2)
        self.assertFalse(out.exists())

    def test_refuses_a_non_empty_output_directory(self):
        out = self.root / 'diagnostics'
        out.mkdir()
        (out / 'keep.txt').write_text('x')
        self.assertEqual(module.main(['--task', str(self.task), '--run-dir', str(self.run_dir),
                                      '--out', str(out)]), 2)
        self.assertTrue((out / 'keep.txt').is_file())

    def test_missing_reports_is_a_usage_error(self):
        out = self.root / 'diagnostics'
        self.assertEqual(module.main(['--task', str(self.task),
                                      '--run-dir', str(self.root / 'nope'), '--out', str(out)]), 2)

    def test_explicit_reports_set_the_order(self):
        out = self.root / 'diagnostics'
        first = self.run_dir / 'trial' / 'push_00.json'
        second = self.run_dir / 'trial' / 'push_01.json'
        self.assertEqual(module.main(['--task', str(self.task), '--report', str(second),
                                      '--report', str(first), '--out', str(out)]), 0)
        result = json.loads((out / 'push_net_displacement.json').read_text())
        self.assertEqual([attempt['report'] for attempt in result['attempts']],
                         ['push_01.json', 'push_00.json'])


if __name__ == '__main__':
    unittest.main()