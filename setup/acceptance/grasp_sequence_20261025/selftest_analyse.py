#!/usr/bin/env python3
"""Adversarial selftest for analyse.py.

A checker that cannot fail proves nothing. Each case below corrupts a private
copy of the archive in a way that contradicts one declared fact, then requires
analyse.py to reject it. The last case is the positive control: untouched bytes
must still pass, otherwise every rejection could be an artefact of the copying.

Run:  python3 setup/acceptance/grasp_sequence_20261025/selftest_analyse.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'grasp_b001_20261025')
ANALYSE = os.path.join(HERE, 'analyse.py')


def read(name):
    rows = []
    with open(os.path.join(SOURCE, name), 'rb') as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line.replace(b'\x00', b'')))
    return rows


def stage(tmp, picks, carry):
    with open(os.path.join(tmp, 'stage_pick.jsonl'), 'w') as fh:
        for row in picks:
            fh.write(json.dumps(row) + '\n')
    with open(os.path.join(tmp, 'stage_carry.jsonl'), 'w') as fh:
        for row in carry:
            fh.write(json.dumps(row) + '\n')


def run(archive):
    proc = subprocess.run([sys.executable, ANALYSE, archive],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def a_untouched_archive_still_passes(tmp):
    """Positive control: the copy, not the analysis, must be what changed."""
    stage(tmp, read('stage_pick.jsonl'), read('stage_carry.jsonl'))
    return 0


@case
def b_injected_failures_relabelled_as_natural(tmp):
    """58 injections counted as physical evidence is the error this exists for."""
    picks = read('stage_pick.jsonl')
    for row in picks:
        if row.get('injected'):
            row.pop('injected')
            row['detail'] = 'box did not follow the lift (rise=-0.001m < 0.030m)'
    stage(tmp, picks, read('stage_carry.jsonl'))
    return 1


@case
def c_failure_starts_from_the_air(tmp):
    """A rise measured from a lifted box is not the same experiment."""
    picks = read('stage_pick.jsonl')
    for row in picks:
        if str(row.get('error_code')) == '23' and row.get('box_before'):
            row['box_before'][2] = 0.0812
    stage(tmp, picks, read('stage_carry.jsonl'))
    return 1


@case
def d_pin_failures_moved_into_failure_windows(tmp):
    """If set_pose_fail really tracked failures, this rewrite would be harmless."""
    picks = read('stage_pick.jsonl')
    carry = read('stage_carry.jsonl')
    for row in carry:
        if row.get('event') == 'set_pose_fail':
            row['wall_ts'] = 0.0
    keep = [c for c in carry if c.get('event') != 'set_pose_fail']
    for row in picks:
        if str(row.get('error_code')) == '23':
            keep.append({'event': 'set_pose_fail', 'object': row.get('object_name'),
                         'consecutive': 1, 'wall_ts': row['wall_ts'] - 0.2})
    stage(tmp, picks, keep)
    return 1


@case
def e_stop_events_given_an_identity(tmp):
    """A stop that names its session would make the attribution gap disappear."""
    carry = read('stage_carry.jsonl')
    for row in carry:
        if row.get('event') == 'stop':
            row['session'] = 'f' * 32
            row['cause'] = 'release'
    stage(tmp, read('stage_pick.jsonl'), carry)
    return 1


@case
def f_failures_clustered_without_changing_any_count(tmp):
    """Sequence dependence made real while every population stays the same size.

    Only wall_ts moves, so the count assertions must still pass; if the script
    still returns 0 then the memorylessness test is not actually testing
    ordering, it is just riding on the counts.
    """
    picks = read('stage_pick.jsonl')
    natural = sorted((r for r in picks if not r.get('injected')),
                     key=lambda r: r['wall_ts'])
    oks = [r for r in natural if str(r.get('error_code')) == '0']
    bads = [r for r in natural if str(r.get('error_code')) == '23']
    base = natural[0]['wall_ts']
    order, i, j = [], 0, 0
    while i < len(oks) or j < len(bads):
        order.extend(oks[i:i + 2])
        i += 2
        order.extend(bads[j:j + 2])
        j += 2
    for index, row in enumerate(order):
        row['wall_ts'] = base + index * 5.0
    stage(tmp, picks, read('stage_carry.jsonl'))
    return 1


def main():
    bad = 0
    for fn in CASES:
        tmp = tempfile.mkdtemp(prefix='seq_selftest_')
        try:
            expected = fn(tmp)
            got, out = run(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = got == expected
        print('%-56s %s  expected=%d got=%d'
              % (fn.__name__, 'PASS' if ok else 'FAIL', expected, got))
        if not ok:
            bad += 1
            tail = [l for l in out.strip().splitlines() if 'FAIL' in l][:4]
            for line in tail:
                print('    %s' % line)
    print('\n%d/%d cases behave as declared' % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
