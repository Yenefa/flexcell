#!/usr/bin/env python3
"""Fixtures for pose_stage_timeline.py: the six alignment groups plus invariants.

Runs with the repository's own Python (no pytest, no ROS):

    python scripts/test_pose_stage_timeline.py

Exit code 0 and a fixture summary when every check holds; exit code 1 otherwise.
Every fixture is synthetic, written under one TemporaryDirectory, and asserts
properties of the TIMELINE: nothing here is a robot, contact or physics result.
"""
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pose_stage_timeline as TIMELINE  # noqa: E402 - path above

SCRIPT = HERE / 'pose_stage_timeline.py'
BASE_NS = 1700000000000000000
MS = 1000000  # ns per millisecond
STATS = {'cases': 0, 'rows': 0, 'codes': set()}


def record(case, rows=0, codes=()):
    STATS['cases'] += 1
    STATS['rows'] += rows
    STATS['codes'].update(codes)


def observation(offset_ms, x, y=0.10, z=0.0175, recv_offset_ms=5, extra=None):
    row = dict(source_stamp_ns=BASE_NS + offset_ms * MS,
               observed_monotonic_ns=BASE_NS + (offset_ms + recv_offset_ms) * MS,
               pose={'x': x, 'y': y, 'z': z, 'orientation': {'w': 1.0}}, channel='topic')
    if extra:
        row.update(extra)
    return row


def phase(offset_ms, name, recv_offset_ms=5):
    return dict(kind='PHASE', phase=name, source_stamp_ns=BASE_NS + offset_ms * MS,
                observed_monotonic_ns=BASE_NS + (offset_ms + recv_offset_ms) * MS)


def dir_digest(directory):
    digest = hashlib.sha256()
    for path in sorted(Path(directory).rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pose-timeline-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / 'run-002'
        self.run.mkdir()

    def write(self, observations, phases, raw_observations=(), raw_phases=()):
        if observations is not None:
            text = ''.join(json.dumps(row) + chr(10) for row in observations)
            text += ''.join(line + chr(10) for line in raw_observations)
            (self.run / 'observations.jsonl').write_text(text, encoding='utf-8')
        if phases is not None:
            text = ''.join(json.dumps(row) + chr(10) for row in phases)
            text += ''.join(line + chr(10) for line in raw_phases)
            (self.run / 'phases.jsonl').write_text(text, encoding='utf-8')

    def build(self, argv=(), out_name=None):
        out = self.root / (out_name or ('out-%02d' % STATS['cases']))
        code = TIMELINE.main([str(self.run), '--out', str(out)] + list(argv))
        return code, out

    def read_summary(self, out):
        return json.loads((out / 'summary.json').read_text(encoding='utf-8'))

    def read_csv(self, out):
        lines = (out / 'timeline.csv').read_text(encoding='utf-8').splitlines()
        header = lines[0].split(',')
        rows = [dict(zip(header, line.split(','))) for line in lines[1:]]
        return header, rows


class AlignmentGroups(Fixture):
    def test_normal_stream_keeps_raw_intervals_and_phase_ages(self):
        self.write([observation(i * 100, 0.20 + 0.01 * i) for i in range(5)],
                   [phase(0, 'APPROACH'), phase(300, 'STROKE')])
        code, out = self.build()
        self.assertEqual(code, 0)
        header, rows = self.read_csv(out)
        self.assertEqual(header, list(TIMELINE.CSV_COLUMNS))
        self.assertEqual(len(rows), 5)
        self.assertEqual([row['phase'] for row in rows],
                         ['APPROACH', 'APPROACH', 'APPROACH', 'STROKE', 'STROKE'])
        self.assertEqual([row['alignable'] for row in rows], ['true'] * 5)
        self.assertEqual([row['reason'] for row in rows], [''] * 5)
        self.assertEqual(rows[0]['interval_ns'], '')
        self.assertEqual([row['interval_ns'] for row in rows[1:]], [str(100 * MS)] * 4)
        self.assertEqual(rows[0]['delta_from_prev'], '')
        for row in rows[1:]:
            self.assertAlmostEqual(float(row['delta_from_prev']), 0.01, places=12)
        self.assertEqual([row['freshness_s'] for row in rows],
                         ['0.0', '0.1', '0.2', '0.0', '0.1'])
        self.assertEqual([row['offset_ms'] for row in rows], ['5.0'] * 5)
        summary = self.read_summary(out)
        self.assertEqual((summary['rows_total'], summary['rows_counted'],
                          summary['rows_unalignable']), (5, 5, 0))
        self.assertEqual(summary['reasons'], {})
        self.assertEqual(summary['phases']['APPROACH']['rows'], 3)
        self.assertEqual(summary['phases']['STROKE']['rows'], 2)
        self.assertEqual(summary['sampling']['intervals_ns'],
                         {'min': 100 * MS, 'median': 100.0 * MS, 'max': 100 * MS})
        stroke = summary['phase_boundaries'][1]
        self.assertEqual((stroke['phase'], stroke['window_ns'], stroke['bounded']),
                         ('STROKE', 100 * MS, True))
        self.assertEqual((stroke['last_sample_before'], stroke['first_sample_after']), (3, 4))
        self.assertFalse(summary['phase_boundaries'][0]['bounded'])
        self.assertEqual(summary['phase_clock_rollbacks'], [])
        self.assertIsNone(summary['phase_ambiguous_from_source_stamp_ns'])
        self.assertEqual([record_['epoch'] for record_ in summary['phase_records']], [1, 1])
        record('normal', 5)

    def test_repeated_snapshot_is_one_measurement_not_two(self):
        # The same world state delivered twice: identical source stamp and pose,
        # received a moment later on the second channel.
        self.write([observation(0, 0.20), observation(100, 0.21),
                    observation(100, 0.21, recv_offset_ms=9),
                    observation(200, 0.22)],
                   [phase(0, 'APPROACH')])
        code, out = self.build()
        self.assertEqual(code, 0)
        header, rows = self.read_csv(out)
        self.assertEqual(len(rows), 4, 'the copy is reported, not dropped')
        self.assertEqual(rows[2]['dup_of'], '2')
        self.assertEqual(rows[2]['reason'], 'DUPLICATE_COPY')
        self.assertEqual(rows[2]['alignable'], 'false')
        self.assertEqual(rows[2]['delta_from_prev'], '')
        self.assertEqual(rows[2]['interval_ns'], '0')
        # the sample after the copy is still one interval away from the kept one
        self.assertAlmostEqual(float(rows[3]['delta_from_prev']), 0.01, places=12)
        summary = self.read_summary(out)
        self.assertEqual((summary['rows_counted'], summary['rows_unalignable']), (3, 1))
        self.assertEqual(summary['duplicates'], {'copies': 1, 'conflicting_stamps': 0})
        self.assertEqual(summary['reasons'], {'DUPLICATE_COPY': 1})
        self.assertEqual(summary['phases']['APPROACH']['rows'], 3)
        record('duplicate_copy', 4, ['DUPLICATE_COPY'])

    def test_out_of_order_sample_is_not_reordered(self):
        self.write([observation(0, 0.20), observation(200, 0.22),
                    observation(100, 0.21), observation(300, 0.23)],
                   [phase(0, 'APPROACH')])
        code, out = self.build()
        self.assertEqual(code, 0)
        _, rows = self.read_csv(out)
        self.assertEqual(rows[2]['reason'], 'OUT_OF_ORDER')
        self.assertEqual(rows[2]['alignable'], 'false')
        self.assertEqual(rows[2]['interval_ns'], str(-100 * MS),
                         'the raw interval is preserved, including its sign')
        self.assertEqual(rows[3]['alignable'], 'true')
        summary = self.read_summary(out)
        self.assertEqual((summary['rows_counted'], summary['rows_unalignable']), (3, 1))
        self.assertEqual(summary['reasons'], {'OUT_OF_ORDER': 1})
        record('out_of_order', 4, ['OUT_OF_ORDER'])

    def test_receipt_clock_rolling_back_is_flagged(self):
        # received 150 ms BEFORE its own source stamp, i.e. earlier than the row
        # that arrived before it: the receipt clock went backwards.
        rows = [observation(0, 0.20), observation(100, 0.21),
                observation(200, 0.22, recv_offset_ms=-150), observation(300, 0.23)]
        self.write(rows, [phase(0, 'APPROACH')])
        code, out = self.build()
        self.assertEqual(code, 0)
        _, csv_rows = self.read_csv(out)
        self.assertEqual(csv_rows[2]['reason'], 'CLOCK_ROLLBACK')
        self.assertEqual(csv_rows[2]['offset_ms'], '-150.0')
        self.assertEqual(csv_rows[3]['alignable'], 'true',
                         'the stream recovers once the receipt clock is monotonic again')
        summary = self.read_summary(out)
        self.assertEqual(summary['reasons'], {'CLOCK_ROLLBACK': 1})
        self.assertEqual(summary['offset_ms']['negative'], 1)
        record('clock_rollback', 4, ['CLOCK_ROLLBACK'])

    def test_samples_before_the_first_phase_have_no_phase(self):
        self.write([observation(i * 100, 0.20 + 0.01 * i) for i in range(4)],
                   [phase(200, 'APPROACH')])
        code, out = self.build()
        self.assertEqual(code, 0)
        _, rows = self.read_csv(out)
        self.assertEqual([row['reason'] for row in rows],
                         ['NO_PHASE_YET', 'NO_PHASE_YET', '', ''])
        self.assertEqual([row['phase'] for row in rows], ['', '', 'APPROACH', 'APPROACH'])
        self.assertEqual(rows[0]['freshness_s'], '')
        self.assertEqual(rows[2]['freshness_s'], '0.0')
        self.assertEqual(rows[3]['freshness_s'], '0.1')
        summary = self.read_summary(out)
        self.assertEqual((summary['rows_counted'], summary['rows_unalignable']), (2, 2))
        self.assertEqual(summary['reasons'], {'NO_PHASE_YET': 2})
        record('missing_phase', 4, ['NO_PHASE_YET'])

    def test_missing_or_non_finite_pose_cannot_be_aligned(self):
        rows = [observation(0, 0.20), dict(source_stamp_ns=BASE_NS + 100 * MS),
                observation(200, 0.22)]
        raw = ['{"source_stamp_ns": %d, "observed_monotonic_ns": %d, '
               '"pose": {"x": NaN, "y": 0.1, "z": 0.0175}}'
               % (BASE_NS + 300 * MS, BASE_NS + 305 * MS)]
        self.write(rows, [phase(0, 'APPROACH')], raw_observations=raw)
        code, out = self.build()
        self.assertEqual(code, 0)
        _, csv_rows = self.read_csv(out)
        self.assertEqual([row['reason'] for row in csv_rows],
                         ['', 'MISSING_POSE', '', 'NON_FINITE_POSE'])
        self.assertEqual(csv_rows[1]['x'], '')
        self.assertEqual(csv_rows[1]['alignable'], 'false')
        self.assertEqual(csv_rows[3]['alignable'], 'false')
        summary = self.read_summary(out)
        self.assertEqual(summary['reasons'], {'MISSING_POSE': 1, 'NON_FINITE_POSE': 1})
        self.assertEqual(summary['rows_counted'], 2)
        record('missing_pose', 4, ['MISSING_POSE', 'NON_FINITE_POSE'])

    def test_phase_clock_rollback_is_not_repaired_by_sorting(self):
        # The phase clock restarts: RETURN arrives after PUSH but carries the earlier
        # stamp. Sorting by stamp alone puts RETURN before PUSH, so the superseded
        # PUSH would govern the later sample and the timeline would look aligned.
        self.write([observation(60, 0.200), observation(95, 0.205), observation(105, 0.210)],
                   [phase(50, 'APPROACH'), phase(100, 'PUSH'), phase(90, 'RETURN')])
        code, out = self.build()
        self.assertEqual(code, 0, 'a rollback is diagnostic output, not a tool failure')
        _, rows = self.read_csv(out)
        self.assertEqual([row['reason'] for row in rows],
                         ['', 'PHASE_CLOCK_ROLLBACK', 'PHASE_CLOCK_ROLLBACK'])
        self.assertEqual([row['phase'] for row in rows], ['APPROACH', '', ''])
        self.assertEqual([row['alignable'] for row in rows], ['true', 'false', 'false'])
        summary = self.read_summary(out)
        self.assertEqual((summary['rows_counted'], summary['rows_unalignable']), (1, 2))
        self.assertEqual(summary['reasons'], {'PHASE_CLOCK_ROLLBACK': 2})
        self.assertEqual(summary['phase_clock_rollbacks'],
                         [dict(index=3, line=3, phase='RETURN',
                               source_stamp_ns=BASE_NS + 90 * MS, epoch=2)])
        self.assertEqual(summary['phase_ambiguous_from_source_stamp_ns'], BASE_NS + 90 * MS)
        # arrival order decides the epoch; the sort order in the summary is by stamp
        self.assertEqual([(record['phase'], record['epoch'])
                          for record in summary['phase_records']],
                         [('APPROACH', 1), ('RETURN', 2), ('PUSH', 1)])
        # A boundary at or above the overlap start could belong to either epoch; the
        # one below it cannot, so only that one stays usable.
        boundaries = {entry['phase']: entry for entry in summary['phase_boundaries']}
        self.assertTrue(boundaries['RETURN']['ambiguous'])
        self.assertTrue(boundaries['PUSH']['ambiguous'])
        self.assertFalse(boundaries['APPROACH']['ambiguous'])
        record('phase_rollback', 3, ['PHASE_CLOCK_ROLLBACK'])

    def test_phase_rollback_reproduction_reports_unknown_not_the_old_phase(self):
        # The review's reproduction, verbatim: PUSH(100) then RETURN(90), sample(105).
        self.write([observation(105, 0.210)],
                   [phase(100, 'PUSH'), phase(90, 'RETURN')])
        code, out = self.build()
        self.assertEqual(code, 0)
        _, rows = self.read_csv(out)
        self.assertEqual(rows[0]['alignable'], 'false')
        self.assertEqual(rows[0]['reason'], 'PHASE_CLOCK_ROLLBACK')
        self.assertEqual(rows[0]['phase'], '', 'the old epoch phase must not be reported')
        summary = self.read_summary(out)
        self.assertEqual(summary['rows_counted'], 0)
        self.assertEqual(summary['phase_ambiguous_from_source_stamp_ns'], BASE_NS + 90 * MS)
        record('phase_rollback_repro', 1, ['PHASE_CLOCK_ROLLBACK'])

    def test_a_conflicting_duplicate_stamp_is_not_a_copy(self):
        self.write([observation(0, 0.20), observation(100, 0.21), observation(100, 0.25)],
                   [phase(0, 'APPROACH')])
        code, out = self.build()
        self.assertEqual(code, 0)
        _, rows = self.read_csv(out)
        self.assertEqual(rows[2]['reason'], 'DUPLICATE_SOURCE_STAMP')
        self.assertEqual(rows[2]['dup_of'], '')
        summary = self.read_summary(out)
        self.assertEqual(summary['duplicates'], {'copies': 0, 'conflicting_stamps': 1})
        self.assertEqual(summary['rows_counted'], 2)
        record('conflicting_stamp', 3, ['DUPLICATE_SOURCE_STAMP'])


class ReadOnlyInvariants(Fixture):
    def test_inputs_are_byte_identical_and_the_output_is_new(self):
        self.write([observation(i * 100, 0.20 + 0.01 * i) for i in range(3)],
                   [phase(0, 'APPROACH')])
        before = dir_digest(self.run)
        out = self.root / 'fresh'
        self.assertFalse(out.exists())
        self.assertEqual(TIMELINE.main([str(self.run), '--out', str(out)]), 0)
        self.assertEqual(before, dir_digest(self.run))
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['summary.json', 'timeline.csv'])
        summary = self.read_summary(out)
        self.assertTrue(summary['inputs_unchanged'])
        for entry in summary['inputs']:
            self.assertEqual(entry['sha256'],
                             hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest())
        record('read_only', 3)

    def test_an_existing_output_directory_is_refused(self):
        self.write([observation(0, 0.20)], [phase(0, 'APPROACH')])
        out = self.root / 'taken'
        out.mkdir()
        (out / 'keep.txt').write_text('untouched')
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = TIMELINE.main([str(self.run), '--out', str(out)])
        self.assertEqual(code, 2)
        self.assertIn('already exists', stderr.getvalue())
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['keep.txt'])
        record('existing_out_refused')

    def test_nothing_is_interpolated_or_resampled(self):
        self.write([observation(i * 100, 0.20 + 0.01 * i) for i in range(4)],
                   [phase(0, 'APPROACH'), phase(150, 'STROKE')])
        code, out = self.build()
        self.assertEqual(code, 0)
        _, rows = self.read_csv(out)
        summary = self.read_summary(out)
        self.assertEqual(len(rows), 4, 'one output row per input sample, never a synthesised one')
        stamps_in = sorted(json.loads(line)['source_stamp_ns'] for line in
                           (self.run / 'observations.jsonl').read_text().splitlines())
        self.assertEqual([int(row['source_stamp_ns']) for row in rows], stamps_in)
        for row in rows[1:]:
            self.assertEqual(int(row['interval_ns']), 100 * MS,
                             'the sampling interval is the raw one')
        self.assertEqual(summary['interpolation'], 'none')
        self.assertEqual(summary['resampling'], 'none')
        self.assertEqual(summary['row_creation'], 'none')
        # the STROKE boundary at 150 ms falls between samples: the window is the
        # raw sample spacing, not a narrowed, interpolated boundary
        stroke = summary['phase_boundaries'][1]
        self.assertEqual((stroke['window_ns'], stroke['bounded']), (100 * MS, True))
        record('no_interpolation', 4)

    def test_repeated_runs_are_deterministic_and_use_new_directories(self):
        self.write([observation(i * 100, 0.20 + 0.01 * i) for i in range(3)],
                   [phase(0, 'APPROACH')])
        self.assertEqual(TIMELINE.main([str(self.run)]), 0)
        self.assertEqual(TIMELINE.main([str(self.run)]), 0)
        produced = sorted(p.name for p in self.root.iterdir()
                          if p.name.startswith('run-002-timeline-'))
        self.assertEqual(len(produced), 2, produced)
        first = self.root / produced[0]
        second = self.root / produced[1]
        self.assertEqual((first / 'timeline.csv').read_bytes(),
                         (second / 'timeline.csv').read_bytes())
        left, right = self.read_summary(first), self.read_summary(second)
        for key in ('generated_utc_ns', 'out_dir'):
            left.pop(key), right.pop(key)
        self.assertEqual(left, right)
        record('deterministic', 3)

    def test_inputs_can_be_given_explicitly(self):
        elsewhere = self.root / 'archive'
        elsewhere.mkdir()
        (elsewhere / 'obs.jsonl').write_text(json.dumps(observation(0, 0.20)) + chr(10))
        (elsewhere / 'ph.jsonl').write_text(json.dumps(phase(0, 'APPROACH')) + chr(10))
        out = self.root / 'explicit-out'
        code = TIMELINE.main([str(self.run), '--out', str(out),
                              '--observations', str(elsewhere / 'obs.jsonl'),
                              '--phases', str(elsewhere / 'ph.jsonl')])
        self.assertEqual(code, 0)
        self.assertEqual(self.read_summary(out)['rows_counted'], 1)
        record('explicit_inputs', 1)


class FailureModes(Fixture):
    def expect_failure(self, argv):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = TIMELINE.main(argv)
        self.assertEqual(code, 2)
        self.assertTrue(stderr.getvalue().strip(), 'a failure must say why')
        return stderr.getvalue()

    def test_missing_run_directory(self):
        self.expect_failure([str(self.root / 'nope'), '--out', str(self.root / 'o')])
        record('failure_missing_run')

    def test_missing_observations_or_phases(self):
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('observations', message)
        self.write([observation(0, 0.20)], None)
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o2')])
        self.assertIn('phases', message)
        record('failure_missing_input')

    def test_empty_observations_are_not_a_timeline(self):
        (self.run / 'observations.jsonl').write_text('')
        (self.run / 'phases.jsonl').write_text(json.dumps(phase(0, 'APPROACH')) + chr(10))
        self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        record('failure_empty')

    def test_malformed_and_non_object_lines(self):
        (self.run / 'phases.jsonl').write_text(json.dumps(phase(0, 'APPROACH')) + chr(10))
        (self.run / 'observations.jsonl').write_text('not json\n')
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('not JSON', message)
        (self.run / 'observations.jsonl').write_text('["not", "an", "object"]\n')
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o2')])
        self.assertIn('not a JSON object', message)
        record('failure_malformed')

    def test_phase_rows_must_carry_a_name_and_a_stamp(self):
        (self.run / 'observations.jsonl').write_text(json.dumps(observation(0, 0.20)) + chr(10))
        (self.run / 'phases.jsonl').write_text(
            json.dumps({'source_stamp_ns': BASE_NS}) + chr(10))
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('phase/stage name', message)
        (self.run / 'phases.jsonl').write_text(json.dumps({'phase': 'APPROACH'}) + chr(10))
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o2')])
        self.assertIn('integer source stamp', message)
        record('failure_bad_phase')

    def test_a_stream_without_source_stamps_is_refused(self):
        (self.run / 'phases.jsonl').write_text(json.dumps(phase(0, 'APPROACH')) + chr(10))
        (self.run / 'observations.jsonl').write_text(
            json.dumps({'channel': 'topic', 'value': 1}) + chr(10))
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('integer source stamp', message)
        record('failure_wrong_shape')

    def test_empty_phase_file_is_an_error_not_a_silent_alignment(self):
        (self.run / 'observations.jsonl').write_text(json.dumps(observation(0, 0.20)) + chr(10))
        (self.run / 'phases.jsonl').write_text('')
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('no records', message)
        record('failure_empty_phase')


class NoVerdict(unittest.TestCase):
    def test_the_output_never_states_causality_or_acceptance(self):
        tmp = tempfile.TemporaryDirectory(prefix='pose-timeline-verdict-')
        self.addCleanup(tmp.cleanup)
        run = Path(tmp.name) / 'run'
        run.mkdir()
        (run / 'observations.jsonl').write_text(json.dumps(observation(0, 0.20)) + chr(10))
        (run / 'phases.jsonl').write_text(json.dumps(phase(0, 'APPROACH')) + chr(10))
        out = Path(tmp.name) / 'out'
        self.assertEqual(TIMELINE.main([str(run), '--out', str(out)]), 0)
        summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        self.assertFalse(summary['causality_claim'])
        self.assertFalse(summary['independent_acceptance_claim'])
        self.assertEqual(summary['interpolation'], 'none')
        self.assertTrue(any('not contact causality' in note for note in summary['notes']))
        forbidden = ('passed', 'pass', 'failed', 'success', 'verdict', 'conclusion',
                     'contact_outcome')
        for key, value in summary.items():
            self.assertNotIn(key.lower(), forbidden, 'timeline output must not name a verdict')
            if isinstance(value, dict):
                for inner in value:
                    self.assertNotIn(inner.lower(), forbidden)
        record('no_verdict')

    def test_documented_statistics_are_what_this_file_exercises(self):
        self.assertGreaterEqual(STATS['cases'], 14)
        self.assertGreaterEqual(STATS['rows'], 28)


class CommandLine(unittest.TestCase):
    def test_the_script_runs_as_a_plain_python_script(self):
        tmp = tempfile.TemporaryDirectory(prefix='pose-timeline-cli-')
        self.addCleanup(tmp.cleanup)
        run = Path(tmp.name) / 'run'
        run.mkdir()
        rows = [observation(0, 0.20), observation(100, 0.21),
                observation(100, 0.21, recv_offset_ms=9)]
        (run / 'observations.jsonl').write_text(''.join(json.dumps(row) + chr(10) for row in rows))
        (run / 'phases.jsonl').write_text(json.dumps(phase(0, 'APPROACH')) + chr(10))
        out = Path(tmp.name) / 'out'
        process = subprocess.run([sys.executable, str(SCRIPT), str(run), '--out', str(out)],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual((summary['rows_counted'], summary['duplicates']['copies']), (2, 1))
        self.assertEqual(json.loads(process.stdout)['rows_counted'], 2)
        record('cli_subprocess')


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    print('')
    print('pose_stage_timeline fixtures: %d cases, %d observation rows written, '
          '%d assertions failed' % (STATS['cases'], STATS['rows'],
                                    len(result.failures) + len(result.errors)))
    print('reason codes exercised: ' + ', '.join(sorted(STATS['codes'])))
    print('alignment groups: normal, duplicate_copy, out_of_order, clock_rollback, '
          'missing_phase, missing_pose (+ conflicting_stamp, no_interpolation, refused inputs)')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
