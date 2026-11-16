#!/usr/bin/env python3
"""Fixture-driven checks for scripts/visual_gate.py.

No robot, no simulator, no pytest: every case builds a SYNTHETIC run directory in
a temporary tree and runs the real gate as a subprocess, so the assertions are on
the exit code and the REASON CODE lines an operator would see.

WHY THE PAIRING TOOL IS SOMETIMES A STAND-IN
    The gate is required to import the acceptance tool rather than keep its own
    copy of the pairing rules, so these tests have to run with that tool present.
    A sparse checkout (no setup/acceptance) does not carry it. There, a contract
    stand-in is written into the temporary tree: what is under test here is the
    GATE - which reason codes fire, what the receipt says, what it refuses to
    write - while the pairing rules themselves are covered by
    src/flexcell/flexcell_skills/test/test_visual_truth_pairing.py, which runs the
    real tool directly. Where the real tool IS present, one case checks the
    stand-in against it, so the two cannot drift unnoticed.

WHAT THESE CASES DO NOT PROVE
    Nothing about a real Gazebo run, a real camera, or the truth sampler: every
    frame and sample here is synthesised. And nothing about the images - the gate
    never opens one, which is the point of the receipt's scope statement.

Run directly:  python scripts/test_visual_gate.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts' / 'visual_gate.py'

#: Same search order the gate uses, resolved once so the cases can say which
#: layout this machine has instead of guessing.
PAIRING_CANDIDATES = (
    ROOT / 'setup' / 'acceptance' / 'evobot_visual_capture_20261111' /
    'scripts' / 'evobot_visual_vs_truth.py',
    ROOT.parent / 'ci-public-window' / 'scripts' / 'evobot_visual_vs_truth.py',
)
REAL_PAIRING = next((path for path in PAIRING_CANDIDATES if path.is_file()), None)

#: The two functions of the pairing tool the gate calls. Documented in the real
#: tool's source; reproduced here only so a checkout without it can still test
#: the gate's own behaviour.
STAND_IN_SOURCE = '''"""Contract stand-in for evobot_visual_vs_truth (test scaffolding, not a tool)."""
DEFAULT_MAX_GAP_S = 1.0


def pair_one(frame_record, truth_samples, max_gap_s=DEFAULT_MAX_GAP_S):
    captured = frame_record.get('captured_wall_ns')
    if not isinstance(captured, int):
        return None, 'frame record has no captured_wall_ns'
    if not truth_samples:
        return None, 'no truth samples were taken'
    best, best_gap = None, None
    for sample in truth_samples:
        wall = sample.get('wall_ns')
        if not isinstance(wall, int):
            continue
        gap = abs(wall - captured) / 1e9
        if best_gap is None or gap < best_gap:
            best, best_gap = sample, gap
    if best is None:
        return None, 'no truth sample carried a usable wall_ns'
    if best_gap > max_gap_s:
        return None, ('closest truth sample is %.3fs away, beyond the %.3fs limit'
                      % (best_gap, max_gap_s))
    objects = best.get('objects') or {}
    if not objects:
        return None, 'closest truth sample contains no objects'
    return dict(frame=str(frame_record.get('path')),
                captured_wall_ns=captured,
                truth_wall_ns=best['wall_ns'],
                pairing_gap_s=round(best_gap, 6),
                truth_source=best.get('source', 'UNKNOWN'),
                objects={name: list(pose) for name, pose in objects.items()}), None


def truth_from_sidecar(frame_record):
    truth = frame_record.get('truth')
    if not isinstance(truth, dict) or not truth.get('available'):
        return None
    if not isinstance(truth.get('objects'), dict) or not truth['objects']:
        return None
    return [dict(wall_ns=truth.get('wall_ns'),
                 source=truth.get('source', 'GZ_GROUND_TRUTH'),
                 objects=truth['objects'])]
'''

POSE = {'target_box_a': [0.22, 0.0, 0.0175]}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def write_json(path, doc):
    return write(path, json.dumps(doc, sort_keys=True) + '\n')


def write_jsonl(path, rows):
    return write(path, ''.join(json.dumps(row, sort_keys=True) + '\n'
                               for row in rows))


def truth_sample(wall_ns, objects=None):
    return dict(wall_ns=wall_ns, source='GZ_GROUND_TRUTH',
                objects=dict(POSE if objects is None else objects))


def frame_row(captured_wall_ns=1_000_000_000, index=0, label=None, image=None):
    """A frame record in the shape the pairing tool expects to receive."""
    row = dict(frame_index=index, sim_ns=10 ** 9 + index,
               monotonic_ns=5_000 + index, valid=True,
               captured_wall_ns=captured_wall_ns)
    if label is not None:
        row['label'] = label
    if image is not None:
        row['image'] = image
    return row


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GateCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='visual-gate-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run_dir = self.base / 'run'
        (self.run_dir / 'data').mkdir(parents=True)
        self.stand_in = write(self.base / 'pairing_stand_in.py', STAND_IN_SOURCE)
        self.pairing_path = REAL_PAIRING or self.stand_in

    # -- running the gate ------------------------------------------------
    def _gate(self, prefix, extra):
        command = ([sys.executable, str(GATE), str(self.run_dir)]
                   + prefix + list(extra))
        return subprocess.run(command, capture_output=True, text=True,
                              cwd=str(ROOT))

    def gate(self, *extra):
        """The gate, pinned to the pairing tool this machine provides."""
        return self._gate(['--pairing-script', str(self.pairing_path)], extra)

    def bare_gate(self, *extra):
        """The gate with no pinned tool: its own search decides."""
        return self._gate([], extra)

    # -- fixtures --------------------------------------------------------
    def frames(self, rows):
        return write_jsonl(self.run_dir / 'data' / 'frames.jsonl', rows)

    def truth(self, samples):
        return write_json(self.run_dir / 'data' / 'truth_samples.json', samples)

    def receipt_path(self):
        return self.run_dir / 'visual_receipt.json'

    def receipt(self):
        return json.loads(self.receipt_path().read_text(encoding='utf-8'))

    def passing_run(self):
        """A run that satisfies every rule; the cases about a pass reuse it."""
        self.frames([frame_row(1_000_000_000, index=0, label='task_start',
                               image='images/000000.png'),
                     frame_row(1_100_000_000, index=1, label='stage_1',
                               image='images/000001.png')])
        self.truth([truth_sample(1_000_000_000), truth_sample(1_050_000_000)])
        return self

    def assert_refused(self, proc, code, receipt_written=False):
        """A refusal is exit 1, names its reason code, and leaves no receipt.

        Per-frame failures are printed as FAILED lines on stdout and run-level
        refusals as a single REFUSED line on stderr, so the code is looked for on
        both streams; the cases that care about the line format pin it themselves.
        """
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(code, proc.stdout + proc.stderr)
        self.assertIn('REFUSED:', proc.stderr)
        self.assertEqual(self.receipt_path().exists(), receipt_written)

    # -- the pass path ---------------------------------------------------
    def test_a_fully_paired_run_passes_and_writes_a_receipt(self):
        self.passing_run()
        proc = self.gate('--objects', 'target_box_a')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertTrue(summary['ok'])
        receipt = self.receipt()
        self.assertEqual(receipt['record_kind'], 'FLEXCELL_VISUAL_GATE_RECEIPT')
        self.assertEqual(receipt['frames_in_manifest'], 2)
        self.assertEqual(receipt['frames_skipped_invalid'], 0)
        self.assertEqual(receipt['frames_seen'], 2)
        self.assertEqual(receipt['frames_paired'], 2)
        self.assertEqual(receipt['pairing_rate'], 1.0)
        self.assertEqual(receipt['max_gap_s'], 1.0)
        self.assertAlmostEqual(receipt['max_pairing_gap_s'], 0.05, places=6)
        self.assertEqual(receipt['objects'], ['target_box_a'])
        self.assertEqual(receipt['objects_seen'], ['target_box_a'])
        self.assertEqual(receipt['truth_sources'], ['GZ_GROUND_TRUTH'])
        self.assertEqual(len(receipt['frame_evidence']), 2)
        self.assertEqual(receipt['frame_evidence'][1]['truth_wall_ns'],
                         1_050_000_000)
        self.assertEqual(receipt['frame_evidence'][0]['objects'],
                         ['target_box_a'])

    def test_the_receipt_says_it_did_not_judge_visual_appearance(self):
        self.passing_run()
        self.assertEqual(self.gate('--objects', 'target_box_a').returncode, 0)
        receipt = self.receipt()
        self.assertIs(receipt['visual_appearance_judged'], False)
        scope = receipt['scope']
        self.assertIn('does NOT', scope)
        self.assertIn('appearance', scope)
        self.assertIn('pixel', scope)
        self.assertIn('recognised', scope)
        # Strict JSON: a receipt with NaN in it would not be readable evidence.
        self.assertNotIn('NaN',
                         json.dumps(self.receipt(), allow_nan=False))
        self.assertIn('does not open the images', receipt['limits'])

    # -- the refusals the gate exists for --------------------------------
    def test_a_frame_whose_truth_is_too_far_away_is_refused(self):
        self.frames([frame_row(1_000_000_000, index=0, label='task_start')])
        self.truth([truth_sample(5_000_000_000)])
        proc = self.gate('--objects', 'target_box_a')
        self.assert_refused(proc, 'FRAME_UNPAIRED')
        self.assertIn('FAILED: FRAME_UNPAIRED', proc.stdout)

    def test_a_run_without_any_truth_sample_is_refused(self):
        self.frames([frame_row(1_000_000_000, index=0)])
        # No truth file at all, and the frame does not carry its own sample.
        self.assert_refused(self.gate('--objects', 'target_box_a'),
                            'NO_TRUTH_SAMPLES')

    def test_a_run_with_an_empty_or_missing_manifest_is_refused(self):
        self.truth([truth_sample(1_000_000_000)])
        write(self.run_dir / 'data' / 'frames.jsonl', '')
        empty = self.gate('--objects', 'target_box_a')
        self.assertEqual(empty.returncode, 1, empty.stdout + empty.stderr)
        self.assertIn('NO_FRAMES', empty.stderr)
        self.assertFalse(self.receipt_path().exists())

        (self.run_dir / 'data' / 'frames.jsonl').unlink()
        absent = self.gate('--objects', 'target_box_a')
        self.assertEqual(absent.returncode, 1, absent.stdout + absent.stderr)
        self.assertIn('NO_FRAMES', absent.stderr)

    def test_a_frame_without_a_capture_stamp_is_refused(self):
        bare = frame_row(1_000_000_000, index=0)
        bare.pop('captured_wall_ns')
        self.frames([bare])
        self.truth([truth_sample(1_000_000_000)])
        self.assert_refused(self.gate('--objects', 'target_box_a'),
                            'FRAME_WITHOUT_CAPTURE_STAMP')
        # The reason says why a simulation stamp is not a substitute.
        self.assertIn('not a wall clock', self.gate(
            '--objects', 'target_box_a').stdout)

    def test_a_declared_object_that_truth_never_measured_fails(self):
        self.frames([frame_row(1_000_000_000, index=0)])
        self.truth([truth_sample(1_000_000_000)])
        proc = self.gate('--objects', 'target_box_a', 'target_box_b')
        self.assert_refused(proc, 'OBJECT_MISSING_FROM_TRUTH')
        self.assertIn('target_box_b', proc.stdout)

    def test_a_non_finite_pose_is_refused(self):
        self.frames([frame_row(1_000_000_000, index=0)])
        # json.loads accepts the NaN token, so nothing upstream rejects it.
        write(self.run_dir / 'data' / 'truth_samples.json',
              '[{"wall_ns": 1000000000, "source": "GZ_GROUND_TRUTH", '
              '"objects": {"target_box_a": [NaN, 0.0, 0.0175]}}]\n')
        proc = self.gate('--objects', 'target_box_a')
        self.assert_refused(proc, 'POSE_NOT_FINITE')
        self.assertIn('target_box_a=', proc.stdout)
        self.assertIn('nan', proc.stdout)

    # -- inputs the gate refuses to invent around ------------------------
    def test_no_declared_objects_is_a_usage_error(self):
        self.passing_run()
        proc = self.gate()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn('NO_DECLARED_OBJECTS', proc.stderr)
        self.assertFalse(self.receipt_path().exists())

    def test_objects_may_be_declared_in_the_run_directory(self):
        self.passing_run()
        write_json(self.run_dir / 'data' / 'objects.json',
                   {'objects': ['target_box_a']})
        proc = self.gate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.receipt()['objects'], ['target_box_a'])

    def test_a_frame_that_carries_its_own_truth_is_paired_from_it(self):
        row = frame_row(1_000_000_000, index=0, label='task_start')
        row['truth'] = dict(available=True, wall_ns=1_000_000_100,
                            source='GZ_GROUND_TRUTH', objects=dict(POSE))
        self.frames([row])
        # No truth file: the refusal for "no samples at all" must not fire when
        # the capture process recorded a sample beside the frame.
        proc = self.gate('--objects', 'target_box_a')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertLess(self.receipt()['max_pairing_gap_s'], 0.001)

    def test_a_row_the_recorder_refused_is_not_graded_but_is_counted(self):
        good = frame_row(1_000_000_000, index=0, label='task_start')
        refused = dict(frame_row(1_000_000_000, index=1), valid=False,
                       reasons=['missing_or_stale_state'])
        self.frames([good, refused])
        self.truth([truth_sample(1_000_000_000)])
        proc = self.gate('--objects', 'target_box_a')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        receipt = self.receipt()
        self.assertEqual(receipt['frames_in_manifest'], 2)
        self.assertEqual(receipt['frames_skipped_invalid'], 1)
        self.assertEqual(receipt['frames_seen'], 1)

    def test_a_manifest_of_only_refused_rows_is_not_evidence_of_capture(self):
        self.frames([dict(frame_row(1_000_000_000, index=0), valid=False)])
        self.truth([truth_sample(1_000_000_000)])
        proc = self.gate('--objects', 'target_box_a')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('NO_FRAMES', proc.stderr)
        self.assertFalse(self.receipt_path().exists())

    def test_a_malformed_frames_line_is_an_input_error(self):
        write(self.run_dir / 'data' / 'frames.jsonl',
              '{"captured_wall_ns": 1000000000}\nnot json\n')
        self.truth([truth_sample(1_000_000_000)])
        proc = self.gate('--objects', 'target_box_a')
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn('MALFORMED_INPUT', proc.stderr)
        self.assertFalse(self.receipt_path().exists())

    def test_an_existing_receipt_is_not_overwritten_without_force(self):
        self.passing_run()
        write(self.receipt_path(), '{"keep": true}\n')
        proc = self.gate('--objects', 'target_box_a')
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(self.receipt_path().read_text()), {'keep': True})
        forced = self.gate('--objects', 'target_box_a', '--force')
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)

    def test_a_forced_failing_recheck_invalidates_the_previous_pass(self):
        """A pass that the latest inputs no longer support must stop being a pass.

        WHY: this tool's pass signal IS the existence of the receipt. Re-checking
        with different inputs and failing while leaving the old receipt untouched
        reports a pass that the current inputs contradict.
        """
        self.passing_run()
        self.assertEqual(self.gate('--objects', 'target_box_a').returncode, 0)
        before = self.receipt()
        # Move the frame away from its truth so the same run can no longer pair.
        self.truth([truth_sample(1_000_000_000, objects={'target_box_a': [0., 0., 0.]})])
        self.frames([frame_row(captured_wall_ns=9_000_000_000, index=0,
                               label='task_start', image='images/000000.png')])
        proc = self.gate('--objects', 'target_box_a', '--force')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('REFUSED:', proc.stderr)
        # No current receipt: the refusal removed the pass signal.
        self.assertFalse(self.receipt_path().exists(), 'a stale pass survived a refusal')
        # ...but the old receipt is kept as history, unchanged and clearly named.
        history = sorted(self.run_dir.glob('visual_receipt.superseded-*.json'))
        self.assertEqual(len(history), 1, history)
        self.assertEqual(json.loads(history[0].read_text(encoding='utf-8')), before)

    def test_a_forced_passing_recheck_replaces_the_receipt(self):
        self.passing_run()
        self.assertEqual(self.gate('--objects', 'target_box_a').returncode, 0)
        first = self.receipt()
        second = self.gate('--objects', 'target_box_a', '--force')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotEqual(self.receipt()['written_wall_ns'],
                            first['written_wall_ns'])
        self.assertEqual(len(list(self.run_dir.glob('visual_receipt.superseded-*.json'))), 1)

    def test_an_unreadable_run_does_not_destroy_an_existing_receipt(self):
        """A refusal to grade is not a verdict, so it must not revoke one."""
        self.passing_run()
        self.assertEqual(self.gate('--objects', 'target_box_a').returncode, 0)
        (self.run_dir / 'data' / 'frames.jsonl').unlink()
        proc = self.gate('--objects', 'target_box_a', '--force')
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertTrue(self.receipt_path().exists(),
                        'an ungradable run revoked a receipt it never judged')

    # -- the tool the gate imports ---------------------------------------
    def test_a_missing_pairing_tool_refuses_by_name_instead_of_passing(self):
        self.passing_run()
        proc = self._gate(['--pairing-script', str(self.base / 'absent.py')], [])
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn('PAIRING_TOOL_NOT_FOUND', proc.stderr)
        self.assertIn('evobot_visual_vs_truth.py', proc.stderr)
        self.assertIn('looked for', proc.stderr)
        self.assertFalse(self.receipt_path().exists())

    def test_the_default_search_finds_the_tool_or_refuses_by_name(self):
        self.passing_run()
        proc = self.bare_gate('--objects', 'target_box_a')
        if REAL_PAIRING is None:
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn('PAIRING_TOOL_NOT_FOUND', proc.stderr)
            self.assertIn('setup', proc.stderr)
            self.assertIn('ci-public-window', proc.stderr)
        else:
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(self.receipt()['frames_paired'], 2)

    def test_the_stand_in_agrees_with_the_real_pairing_tool(self):
        """Only meaningful where the checkout carries the real tool."""
        if REAL_PAIRING is None:
            self.skipTest('real pairing tool is not in this checkout; the gate '
                          'cases above ran against the contract stand-in')
        real = load_module(REAL_PAIRING, 'real_pairing_tool')
        sand = load_module(self.stand_in, 'stand_in_pairing_tool')
        cases = [
            (frame_row(1_000_000_000), [truth_sample(1_000_000_000)], 1.0),
            (frame_row(1_000_000_000), [truth_sample(1_050_000_000)], 1.0),
            (frame_row(1_000_000_000), [truth_sample(5_000_000_000)], 1.0),
            (frame_row(1_000_000_000), [], 1.0),
            (dict(frame_row(1_000_000_000), objects={}),
             [truth_sample(1_000_000_000, objects={})], 1.0),
            ({'frame': '/tmp/a.png'}, [truth_sample(1_000_000_000)], 1.0),
        ]
        for frame, samples, max_gap in cases:
            theirs = real.pair_one(dict(frame), samples, max_gap)
            ours = sand.pair_one(dict(frame), samples, max_gap)
            self.assertEqual(theirs[0] is None, ours[0] is None,
                             '%r -> %r vs %r' % (frame, theirs[1], ours[1]))
            if theirs[0] is not None:
                self.assertEqual(theirs[0]['truth_wall_ns'],
                                 ours[0]['truth_wall_ns'])
                self.assertEqual(theirs[0]['pairing_gap_s'],
                                 ours[0]['pairing_gap_s'])
                self.assertEqual(theirs[0]['objects'], ours[0]['objects'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
