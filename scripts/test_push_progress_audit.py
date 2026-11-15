#!/usr/bin/env python3
"""Fixtures for push_progress_audit.py: 6 boundary classes plus input invariants.

Runs with the repository's own Python (no pytest, no ROS):

    python scripts/test_push_progress_audit.py

Exit code 0 and a fixture summary when every check holds; exit code 1 otherwise.
All fixtures are synthetic and are written to a temporary directory: this file
asserts properties of the AUDIT, never of a robot run. Every fixture's run and
output directories live under one TemporaryDirectory that is removed on exit.
"""
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import push_progress_audit as AUDIT  # noqa: E402 - path above
from push_progress_audit import SKILLS_ROOT  # noqa: E402

if str(SKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLS_ROOT))
from flexcell_skills.contracts import push_recover as CONTRACT  # noqa: E402

# A 3-4-5 direction keeps every projection exact in decimal arithmetic, so a
# failure here is a logic failure and not a rounding coincidence.
UNIT = (0.6, 0.8)
SCRIPT = HERE / 'push_progress_audit.py'
STATS = {'cases': 0, 'rows': 0, 'codes': set()}


def record(case, rows=0, codes=()):
    STATS['cases'] += 1
    STATS['rows'] += rows
    STATS['codes'].update(codes)


def pose(x, y, z=0.0175):
    return {'position': {'x': x, 'y': y, 'z': z}, 'orientation': {'w': 1.0}}


def attempt(before=None, after=None, along=None, magnitude=None, contact=True,
            carry=False, name='target_box_a', extra=None):
    row = dict(request_id='push', object_name=name, contact_made=contact,
               carry_engaged_during=carry)
    if along is not None:
        row['displacement_along_direction_m'] = along
    if magnitude is not None:
        row['displacement_m'] = magnitude
    if before is not None:
        row['measured_before'] = before
    if after is not None:
        row['measured_after'] = after
    if extra:
        row.update(extra)
    return row


def move(origin, distance, unit=UNIT):
    return (origin[0] + unit[0] * distance, origin[1] + unit[1] * distance)


def dir_digest(directory):
    """sha256 over every file under directory: proves the input was not touched."""
    digest = hashlib.sha256()
    for path in sorted(Path(directory).rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='push-audit-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / 'run-001'
        self.run.mkdir()

    def write(self, rows, name='push_attempts.jsonl', raw=()):
        """rows: dicts serialized as JSON; raw: pre-serialized lines (NaN/Infinity)."""
        target = self.run / name
        text = ''.join(json.dumps(row) + chr(10) for row in rows) + ''.join(
            line + chr(10) for line in raw)
        target.write_text(text, encoding='utf-8')
        return target

    def audit(self, argv=(), direction=None):
        out = self.root / ('out-%02d' % STATS['cases'])
        args = [str(self.run), '--out', str(out)]
        if direction is not None:
            args += ['--direction', direction]
        args += list(argv)
        code = AUDIT.main(args)
        return code, out

    def read_summary(self, out):
        return json.loads((out / 'summary.json').read_text(encoding='utf-8'))

    def read_csv(self, out):
        lines = (out / 'attempts.csv').read_text(encoding='utf-8').splitlines()
        header = lines[0].split(',')
        rows = [dict(zip(header, line.split(','))) for line in lines[1:]]
        return header, rows


class BoundaryClasses(Fixture):
    """The six classes the issue names, plus the two fallback paths."""

    def test_forward_reports_progress_and_net_agree(self):
        rows = [
            attempt(pose(0.20, 0.10), pose(0.2186, 0.1248), along=0.031, magnitude=0.031),
            attempt(pose(0.2186, 0.1248), pose(0.2138, 0.1184), along=-0.008, magnitude=0.008),
            attempt(pose(0.2138, 0.1184), pose(0.2318, 0.1424), along=0.030, magnitude=0.030),
        ]
        self.write(rows)
        code, out = self.audit(direction='0.6,0.8')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual(summary['status'], 'MEASURED')
        self.assertEqual((summary['sign'], summary['code']), ('POSITIVE', 'OK'))
        self.assertAlmostEqual(summary['reported_total_m'], 0.053, places=9)
        self.assertAlmostEqual(summary['signed_net_total_m'], 0.053, places=9)
        self.assertAlmostEqual(summary['difference_total_m'], 0.0, places=9)
        # The policy zeroes the backwards attempt instead of subtracting it, so the
        # number a retry loop accumulates overstates real motion by exactly that 8 mm.
        self.assertAlmostEqual(summary['reported_counted_total_m'], 0.061, places=9)
        self.assertAlmostEqual(summary['counted_minus_net_m'], 0.008, places=9)
        header, csv_rows = self.read_csv(out)
        self.assertEqual(header, list(AUDIT.CSV_COLUMNS))
        self.assertEqual(len(csv_rows), 3)
        self.assertEqual(csv_rows[1]['code'], 'MOVED_BACKWARDS')
        self.assertEqual(csv_rows[1]['reported_counted_m'], '0.0')
        self.assertEqual(csv_rows[1]['sign'], 'NEGATIVE')
        self.assertEqual(csv_rows[1]['contact_made'], 'true')
        self.assertEqual(csv_rows[1]['clears_floor'], 'false')
        self.assertEqual(summary['signed_source_counts'], {'along': 3})
        self.assertEqual(summary['attempts_clearing_floor'], 2)
        record('forward', 3, ['OK', 'MOVED_BACKWARDS'])

    def test_backward_motion_is_negative_not_unsigned(self):
        rows = [
            attempt(pose(0.30, 0.10), pose(0.28, 0.10), along=-0.02, magnitude=0.02),
            attempt(pose(0.28, 0.10), pose(0.27, 0.10), along=-0.01, magnitude=0.01),
        ]
        self.write(rows)
        code, out = self.audit(direction='1,0')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual((summary['status'], summary['sign']), ('MEASURED', 'NEGATIVE'))
        self.assertAlmostEqual(summary['signed_net_total_m'], -0.03, places=9)
        self.assertAlmostEqual(summary['reported_total_m'], -0.03, places=9)
        self.assertEqual(summary['reported_counted_total_m'], 0.0)
        self.assertAlmostEqual(summary['counted_minus_net_m'], 0.03, places=9)
        record('backward', 2, ['MOVED_BACKWARDS'])

    def test_lateral_motion_cannot_supply_a_sign(self):
        rows = [
            attempt(pose(0.20, 0.10), pose(0.20, 0.13), along=0.0002, magnitude=0.03),
            attempt(pose(0.20, 0.13), pose(0.20, 0.15), along=0.0001, magnitude=0.02),
        ]
        self.write(rows)
        code, out = self.audit(direction='1,0')
        self.assertEqual(code, 0, 'UNKNOWN is a diagnostic answer, not a tool failure')
        summary = self.read_summary(out)
        self.assertEqual((summary['status'], summary['sign'], summary['code']),
                         ('UNKNOWN', 'UNKNOWN', 'ZERO_PROJECTION'))
        # The net IS measured (zero along the direction); only its sign is undefined.
        self.assertAlmostEqual(summary['signed_net_total_m'], 0.0, places=12)
        self.assertAlmostEqual(summary['difference_total_m'], 0.0003, places=9)
        _, csv_rows = self.read_csv(out)
        self.assertEqual([row['net_code'] for row in csv_rows], ['ZERO_PROJECTION'] * 2)
        record('lateral', 2, ['ZERO_PROJECTION'])

    def test_static_object_reports_no_motion(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.20, 0.10), along=0.0, magnitude=0.0),
                attempt(pose(0.20, 0.10), pose(0.20, 0.10), along=0.0004, magnitude=0.0004)]
        self.write(rows)
        code, out = self.audit(direction='0.6,0.8')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual((summary['status'], summary['sign'], summary['code']),
                         ('UNKNOWN', 'UNKNOWN', 'NO_MOTION'))
        self.assertAlmostEqual(summary['signed_net_total_m'], 0.0, places=12)
        record('static', 2, ['NO_MOTION'])

    def test_missing_endpoint_leaves_the_run_net_unknown(self):
        rows = [
            attempt(pose(0.20, 0.10), pose(0.23, 0.10), along=0.03, magnitude=0.03),
            attempt(pose(0.23, 0.10), pose(0.26, 0.10), along=0.03, magnitude=0.03),
            # last attempt never returned a post pose: the run's own window is open
            attempt(pose(0.26, 0.10), None, along=0.01, magnitude=0.01),
        ]
        self.write(rows)
        code, out = self.audit(direction='1,0')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual((summary['status'], summary['sign'], summary['code']),
                         ('UNKNOWN', 'UNKNOWN', 'MISSING_ENDPOINT'))
        self.assertEqual(summary['endpoints']['reason'], 'MISSING_ENDPOINT')
        self.assertIsNone(summary['signed_net_total_m'])
        self.assertEqual(summary['partial_window']['start_row'], 1)
        self.assertEqual(summary['partial_window']['end_row'], 2)
        self.assertIn('sub-window', summary['partial_window']['note'])
        # once on the open last attempt, once on the run-level code
        self.assertEqual(summary['reasons']['MISSING_ENDPOINT'], 2)
        _, csv_rows = self.read_csv(out)
        self.assertEqual(csv_rows[2]['net_code'], 'MISSING_ENDPOINT')
        self.assertEqual(csv_rows[2]['signed_net_m'], '')
        record('missing_endpoint', 3, ['MISSING_ENDPOINT'])

    def test_non_finite_report_makes_the_audit_unknown_but_keeps_the_net(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.2186, 0.1248), along=0.031, magnitude=0.031),
                attempt(pose(0.2186, 0.1248), pose(0.2318, 0.1424), along=0.030, magnitude=0.030)]
        # contact_push_server initialises the displacement fields to NaN before it
        # measures, so a NaN literal is a real archive shape, not a synthetic one.
        self.write(rows, raw=['{"object_name": "target_box_a", "contact_made": false, '
                              '"carry_engaged_during": false, '
                              '"displacement_along_direction_m": NaN, "displacement_m": NaN, '
                              '"measured_before": {"position": {"x": 0.2318, "y": 0.1424}}, '
                              '"measured_after": {"position": {"x": 0.2318, "y": 0.1424}}}'])
        code, out = self.audit(direction='0.6,0.8')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual((summary['status'], summary['code']), ('UNKNOWN', 'NON_FINITE'))
        # The net is still measured: "the report is unusable" and "the object did
        # not move" are different statements and must not be merged.
        self.assertEqual(summary['sign'], 'POSITIVE')
        self.assertEqual(summary['reasons']['NON_FINITE_REPORT'], 1)
        self.assertAlmostEqual(summary['signed_net_total_m'], 0.053, places=9)
        self.assertFalse(summary['reported_total_complete'])
        self.assertIsNone(summary['difference_total_m'],
                          'a total over an incomplete report cannot be differenced '
                          'against the net')
        _, csv_rows = self.read_csv(out)
        self.assertEqual(csv_rows[2]['code'], 'NON_FINITE_REPORT')
        self.assertEqual(csv_rows[2]['reported_progress_m'], '')
        record('non_finite', 3, ['NON_FINITE', 'NON_FINITE_REPORT'])

    def test_unsigned_fallback_hides_a_backward_attempt(self):
        rows = [
            attempt(pose(0.20, 0.10), pose(0.2186, 0.1248), magnitude=0.031),
            attempt(pose(0.2186, 0.1248), pose(0.2138, 0.1184), magnitude=0.008),
            attempt(pose(0.2138, 0.1184), pose(0.2318, 0.1424), magnitude=0.030),
        ]
        self.write(rows)
        code, out = self.audit(direction='0.6,0.8')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual(summary['signed_source_counts'], {'fallback': 3})
        self.assertAlmostEqual(summary['reported_total_m'], 0.069, places=9)
        self.assertAlmostEqual(summary['signed_net_total_m'], 0.053, places=9)
        self.assertAlmostEqual(summary['difference_total_m'], 0.016, places=9)
        self.assertTrue(any('unsigned magnitude' in caveat for caveat in summary['caveats']))
        record('fallback', 3, ['OK'])

    def test_over_reported_attempt_shows_up_as_a_difference(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.225, 0.10), along=0.040, magnitude=0.040)]
        self.write(rows)
        code, out = self.audit(direction='1,0')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertAlmostEqual(summary['difference_total_m'], 0.015, places=9)
        self.assertEqual(summary['rows_reported_off_by_more_than_floor'], 1)
        self.assertEqual(summary['sign'], 'POSITIVE')
        record('over_report', 1, ['OK'])

    def test_direction_is_derived_and_labelled_when_not_given(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.2318, 0.1424), along=0.053, magnitude=0.053)]
        self.write(rows)
        code, out = self.audit()
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual(summary['direction']['source'], 'derived')
        self.assertAlmostEqual(summary['direction']['unit'][0], 0.6, places=12)
        self.assertAlmostEqual(summary['direction']['unit'][1], 0.8, places=12)
        self.assertTrue(any('derived' in caveat for caveat in summary['caveats']))
        record('derived_direction', 1)


class ReadOnlyInvariants(Fixture):
    def test_input_is_byte_identical_and_output_is_a_new_directory(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.2318, 0.1424), along=0.053, magnitude=0.053)]
        self.write(rows)
        before = dir_digest(self.run)
        out = self.root / 'new-out'
        self.assertFalse(out.exists())
        self.assertEqual(AUDIT.main([str(self.run), '--out', str(out), '--direction', '1,0']), 0)
        self.assertEqual(before, dir_digest(self.run))
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['attempts.csv', 'summary.json'])
        summary = self.read_summary(out)
        self.assertTrue(summary['inputs_unchanged'])
        self.assertEqual(summary['inputs'][0]['sha256'],
                         hashlib.sha256((self.run / 'push_attempts.jsonl').read_bytes()).hexdigest())
        record('read_only')

    def test_an_existing_output_directory_is_refused(self):
        self.write([attempt(pose(0.20, 0.10), pose(0.2318, 0.1424), along=0.053, magnitude=0.053)])
        out = self.root / 'taken'
        out.mkdir()
        (out / 'keep.txt').write_text('untouched')
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = AUDIT.main([str(self.run), '--out', str(out), '--direction', '1,0'])
        self.assertEqual(code, 2)
        self.assertIn('already exists', stderr.getvalue())
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['keep.txt'])
        record('existing_out_refused')

    def test_a_second_default_run_never_reuses_the_first_directory(self):
        self.write([attempt(pose(0.20, 0.10), pose(0.2318, 0.1424), along=0.053, magnitude=0.053)])
        self.assertEqual(AUDIT.main([str(self.run), '--direction', '1,0']), 0)
        self.assertEqual(AUDIT.main([str(self.run), '--direction', '1,0']), 0)
        produced = sorted(p.name for p in self.root.iterdir() if p.name.startswith('run-001-audit-'))
        self.assertEqual(len(produced), 2, produced)
        self.assertEqual(dir_digest(self.run),
                         dir_digest(self.run), 'the run directory is never a destination')
        record('default_out_twice')

    def test_repeated_audits_are_deterministic(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.2186, 0.1248), along=0.031, magnitude=0.031),
                attempt(pose(0.2186, 0.1248), pose(0.2138, 0.1184), along=-0.008, magnitude=0.008)]
        self.write(rows)
        code, first = self.audit(direction='0.6,0.8')
        self.assertEqual(code, 0)
        STATS['cases'] -= 1  # the second audit reuses the same fixture generation
        second = self.root / 'out-again'
        self.assertEqual(AUDIT.main([str(self.run), '--out', str(second),
                                     '--direction', '0.6,0.8']), 0)
        self.assertEqual((first / 'attempts.csv').read_bytes(),
                         (second / 'attempts.csv').read_bytes())
        left, right = self.read_summary(first), self.read_summary(second)
        for key in ('generated_utc_ns', 'out_dir'):
            left.pop(key), right.pop(key)
        self.assertEqual(left, right)
        record('deterministic', 2)


class FailureModes(Fixture):
    def expect_failure(self, argv):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = AUDIT.main(argv)
        self.assertEqual(code, 2)
        self.assertTrue(stderr.getvalue().strip(), 'a failure must say why')
        return stderr.getvalue()

    def test_missing_run_directory(self):
        self.expect_failure([str(self.root / 'nope'), '--out', str(self.root / 'o')])
        record('failure_missing_run')

    def test_no_attempts_file(self):
        self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        record('failure_no_attempts')

    def test_empty_and_malformed_attempts(self):
        (self.run / 'push_attempts.jsonl').write_text('')
        self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        (self.run / 'push_attempts.jsonl').write_text('{"a": 1}\nnot json\n')
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o2')])
        self.assertIn('not JSON', message)
        record('failure_bad_attempts')

    def test_ambiguous_object_identity(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.23, 0.10), along=0.03, name='target_box_a'),
                attempt(pose(0.23, 0.10), pose(0.26, 0.10), along=0.03, name='target_box_b')]
        self.write(rows)
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('several objects', message)
        record('failure_multi_object')

    def test_direction_arguments_are_validated(self):
        self.write([attempt(pose(0.20, 0.10), pose(0.2318, 0.1424), along=0.053)])
        for bad in ('0,0', 'nan,1', 'inf,0'):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    AUDIT.main([str(self.run), '--out', str(self.root / ('d-' + bad[0])),
                                '--direction', bad])
            self.assertEqual(caught.exception.code, 2, bad)
        with contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as caught:
            AUDIT.main([str(self.run), '--out', str(self.root / 'd-x'), '--direction', 'east'])
        self.assertEqual(caught.exception.code, 2)
        record('failure_bad_direction')

    def test_unreadable_result_is_a_row_not_a_crash(self):
        self.write([attempt(pose(0.20, 0.10), pose(0.23, 0.10), along=0.03, magnitude=0.03)],
                   raw=['["not", "an", "object"]'])
        code, out = self.audit(direction='1,0')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        self.assertEqual(summary['reasons']['UNREADABLE_RESULT'], 1)
        self.assertEqual(summary['code'], 'MISSING_ENDPOINT')
        self.assertEqual(summary['status'], 'UNKNOWN')
        record('unreadable_row', 2, ['UNREADABLE_RESULT'])

    def test_a_file_without_recognised_fields_is_refused(self):
        self.write([], raw=['{"channel": "topic", "value": 1}'])
        message = self.expect_failure([str(self.run), '--out', str(self.root / 'o')])
        self.assertIn('recognised displacement', message)
        record('failure_wrong_shape')


class ContractReuse(Fixture):
    def test_judging_primitives_are_the_frozen_contract_objects(self):
        self.assertIs(AUDIT.classify_attempt, CONTRACT.classify_attempt)
        self.assertIs(AUDIT.is_progress, CONTRACT.is_progress)
        self.assertEqual(AUDIT.MIN_DISPLACEMENT_M, CONTRACT.MIN_DISPLACEMENT_M)
        self.assertEqual(AUDIT.MIN_DISPLACEMENT_M, 0.005)

    def test_counted_column_is_what_the_policy_would_accumulate(self):
        rows = [attempt(pose(0.20, 0.10), pose(0.2186, 0.1248), along=0.031, magnitude=0.031),
                attempt(pose(0.2186, 0.1248), pose(0.2138, 0.1184), along=-0.008, magnitude=0.008),
                dict(object_name='target_box_a', carry_engaged_during=True, contact_made=True,
                     displacement_along_direction_m=0.05, displacement_m=0.05,
                     measured_before=pose(0.2138, 0.1184), measured_after=pose(0.2413, 0.155))]
        self.write(rows)
        code, out = self.audit(direction='0.6,0.8')
        self.assertEqual(code, 0)
        summary = self.read_summary(out)
        expected = 0.0
        for row in rows:
            _, moved, _, _ = CONTRACT.classify_attempt(row)
            expected += moved
        self.assertAlmostEqual(summary['reported_counted_total_m'], expected, places=12)
        self.assertEqual(summary['carry_engaged_attempts'], 1)
        self.assertEqual(summary['reasons']['CARRIED'], 1)
        record('contract_counted', 3, ['CARRIED'])

    def test_floor_is_taken_from_the_contract_not_reinvented(self):
        just_below = CONTRACT.MIN_DISPLACEMENT_M * 0.9
        just_above = CONTRACT.MIN_DISPLACEMENT_M * 1.1
        self.assertFalse(CONTRACT.is_progress(just_below))
        self.assertTrue(CONTRACT.is_progress(just_above))
        self.assertEqual(AUDIT.classify_sign(just_below, just_below)[1], 'NO_MOTION')
        self.assertEqual(AUDIT.classify_sign(just_above, just_above)[0], 'POSITIVE')
        record('floor_reused')


class NoVerdict(unittest.TestCase):
    def test_the_output_never_states_a_task_outcome(self):
        tmp = tempfile.TemporaryDirectory(prefix='push-audit-verdict-')
        self.addCleanup(tmp.cleanup)
        run = Path(tmp.name) / 'run'
        run.mkdir()
        (run / 'push_attempts.jsonl').write_text(json.dumps(
            attempt(pose(0.20, 0.10), pose(0.2318, 0.1424), along=0.053, magnitude=0.053)) + chr(10))
        out = Path(tmp.name) / 'out'
        self.assertEqual(AUDIT.main([str(run), '--out', str(out), '--direction', '1,0']), 0)
        summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        self.assertFalse(summary['task_success_claim'])
        self.assertFalse(summary['independent_acceptance_claim'])
        self.assertFalse(summary['policy_modified'])
        self.assertFalse(summary['interpolation_used'])
        forbidden = ('passed', 'pass', 'failed', 'success', 'verdict', 'conclusion', 'outcome')
        for key, value in summary.items():
            self.assertNotIn(key.lower(), forbidden, 'audit output must not name a verdict')
            if isinstance(value, dict):
                for inner in value:
                    self.assertNotIn(inner.lower(), forbidden)
        record('no_verdict')

    def test_documented_statistics_are_what_this_file_exercises(self):
        # Guard against a fixture set that silently stops covering a class.
        self.assertGreaterEqual(STATS['cases'], 17)
        self.assertGreaterEqual(STATS['rows'], 20)


class CommandLine(unittest.TestCase):
    def test_the_script_runs_as_a_plain_python_script(self):
        tmp = tempfile.TemporaryDirectory(prefix='push-audit-cli-')
        self.addCleanup(tmp.cleanup)
        run = Path(tmp.name) / 'run'
        run.mkdir()
        (run / 'push_attempts.jsonl').write_text(json.dumps(
            attempt(pose(0.30, 0.10), pose(0.27, 0.10), along=-0.03, magnitude=0.03)) + chr(10))
        out = Path(tmp.name) / 'out'
        process = subprocess.run([sys.executable, str(SCRIPT), str(run), '--out', str(out),
                                  '--direction', '1,0'],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['sign'], 'NEGATIVE')
        self.assertEqual(json.loads(process.stdout)['sign'], 'NEGATIVE')
        record('cli_subprocess')


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    print('')
    print('push_progress_audit fixtures: %d cases, %d attempt rows written, %d assertions failed'
          % (STATS['cases'], STATS['rows'], len(result.failures) + len(result.errors)))
    print('reason codes exercised: ' + ', '.join(sorted(STATS['codes'])))
    print('boundary classes: forward, backward, lateral, static, missing_endpoint, non_finite'
          ' (+ fallback, derived, over-report, unreadable, carried, refused inputs)')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
