#!/usr/bin/env python3
"""Adversarial selftest for verify_phase3_window.py.

A checker that cannot fail proves nothing. Each case copies the archive to a
temporary directory, contradicts one declared fact, and requires a non-zero
exit. The first case is the positive control: an untouched copy must pass, so a
rejection cannot be an artefact of copying.

Run:  python3 selftest_verify_phase3_window.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, 'verify_phase3_window.py')
HIST = os.path.join(os.path.dirname(HERE), 'grasp_b001_20261025')


def copy_archive(tmp):
    dst = os.path.join(tmp, 'archive')
    shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns('__pycache__'))
    return dst


def rewrite(path, fn):
    rows = []
    with open(path, 'rb') as fh:
        for line in fh:
            if not line.strip():
                continue
            rows.append(json.loads(line.replace(b'\x00', b'')))
    rows = fn(rows)
    with open(path, 'w') as fh:
        for row in rows:
            fh.write(json.dumps(row) + '\n')


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def a_untouched_archive_still_passes(root):
    return 0


@case
def b_the_failure_relabelled_as_success(root):
    def edit(rows):
        for row in rows:
            if not row.get('pick_ok'):
                row['pick_ok'] = True
                row['error_code'] = 0
        return rows
    rewrite(os.path.join(root, 'B5.jsonl'), edit)
    return 1


@case
def c_a_missing_lookup_hidden_in_one_summary(root):
    """Counts are cumulative, so the totals live in the LAST summary per
    session; the mutation must reach it to contradict the zero-miss claim."""
    def edit(rows):
        for row in rows:
            if row.get('event') == 'teleport_loop_summary':
                row['ee_missing_count'] = 9
        return rows
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def c2_only_the_last_summary_per_session_altered(root):
    """A subtler version: touch only the record the checker actually reads."""
    def edit(rows):
        last_of = {}
        for row in rows:
            if row.get('event') == 'teleport_loop_summary':
                last_of[row['session']] = row
        for row in last_of.values():
            row['ee_missing_count'] = 4
        return rows
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def c3_a_non_final_record_pushed_to_the_end(root):
    """Truncation: the summaries stop at a periodic record instead of a final."""
    def edit(rows):
        summaries = [r for r in rows
                     if r.get('event') == 'teleport_loop_summary']
        others = [r for r in rows
                  if r.get('event') != 'teleport_loop_summary']
        kept = [r for r in summaries if not r.get('final')]
        return others + kept
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def d_extra_pin_failures_added(root):
    def edit(rows):
        for row in rows:
            if row.get('event') == 'teleport_loop_summary':
                row['pin_failed'] = 6
        return rows
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def e_the_final_summary_dropped(root):
    def edit(rows):
        keep, dropped = [], False
        for row in rows:
            if row.get('event') == 'teleport_loop_summary' and row.get('final') and not dropped:
                dropped = True
                continue
            keep.append(row)
        return keep
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def f_the_failure_moved_into_the_historical_shape(root):
    def edit(rows):
        for row in rows:
            if row.get('object_name') == 'target_box_b' and not row.get('pick_ok'):
                row['after'] = [0.2, -0.18, 0.0055]
                row['rise_m'] = -0.0120
        return rows
    rewrite(os.path.join(root, 'B5.jsonl'), edit)

    def edit_picks(rows):
        for row in rows:
            if str(row.get('error_code')) == '23':
                row['box_after'] = [0.2, -0.18, 0.0055]
                row['box_rise_m'] = -0.0120
        return rows
    rewrite(os.path.join(root, 'logs', 'pick_window.jsonl'), edit_picks)
    return 1


def run(root):
    proc = subprocess.run([sys.executable, VERIFY, root, HIST],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    bad = 0
    for fn in CASES:
        tmp = tempfile.mkdtemp(prefix='p3_selftest_')
        try:
            root = copy_archive(tmp)
            expected = fn(root)
            got, out = run(root)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = got == expected
        print('%-52s %s  expected=%d got=%d'
              % (fn.__name__, 'PASS' if ok else 'FAIL', expected, got))
        if not ok:
            bad += 1
            for line in out.strip().splitlines():
                if 'FAIL' in line:
                    print('    %s' % line)
    print('\n%d/%d cases behave as declared' % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
