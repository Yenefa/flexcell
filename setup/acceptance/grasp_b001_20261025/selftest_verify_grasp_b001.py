#!/usr/bin/env python3
"""Adversarial self-test for verify_grasp_b001.py.

A checker that cannot fail proves nothing. Each case copies the archive into a
scratch directory, applies one falsification, and requires the verifier to
reject it. Case A is the only one that may exit 0.

Pure stdlib. No ROS, no network.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFIER = HERE / 'verify_grasp_b001.py'


def run(root):
    result = subprocess.run([sys.executable, str(Path(root) / VERIFIER.name)],
                            capture_output=True, text=True)
    return result.returncode, result.stdout


def scratch():
    tmp = Path(tempfile.mkdtemp(prefix='graspb001_selftest_'))
    target = tmp / 'archive'
    shutil.copytree(HERE, target, ignore=shutil.ignore_patterns(
        'selftest_*', '__pycache__'))
    return tmp, target


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def write_jsonl(path, rows):
    Path(path).write_text(
        ''.join(json.dumps(r, allow_nan=False) + '\n' for r in rows), encoding='utf-8')


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def a_clean_archive_passes(root):
    return None  # no mutation


@case
def b_lowered_rise_rejected(root):
    rows = read_jsonl(root / 'A.jsonl')
    rows[3]['rise_m'] = 0.02
    rows[3]['after'][2] = rows[3]['before'][2] + 0.02
    write_jsonl(root / 'A.jsonl', rows)


@case
def c_deleted_trial_rejected(root):
    rows = read_jsonl(root / 'B.jsonl')
    write_jsonl(root / 'B.jsonl', rows[:-1])


@case
def d_injected_harness_error_rejected(root):
    rows = read_jsonl(root / 'A.jsonl')
    rows[0]['harness_error'] = 'goal acceptance timed out; acceptance unknown'
    write_jsonl(root / 'A.jsonl', rows)


@case
def e_nonzero_exit_rejected(root):
    (root / 'B.exit').write_text('1\n', encoding='utf-8')


@case
def f_dirty_health_rejected(root):
    data = json.loads((root / 'health_after.json').read_text(encoding='utf-8'))
    data['checks']['task_state'] = 'RUNNING'
    (root / 'health_after.json').write_text(json.dumps(data), encoding='utf-8')


@case
def g_wrong_commit_rejected(root):
    head = (root / 'head.txt').read_text(encoding='utf-8').splitlines()
    head[0] = '0' * 40
    (root / 'head.txt').write_text('\n'.join(head) + '\n', encoding='utf-8')


@case
def h_missing_historical_evidence_rejected(root):
    rows = read_jsonl(root / 'stage_pick.jsonl')
    write_jsonl(root / 'stage_pick.jsonl',
                [r for r in rows if r.get('evidence_id') != 'target_box_a-2d6775e0'])


@case
def i_overlapping_populations_rejected(root):
    rows = read_jsonl(root / 'stage_pick.jsonl')
    for r in rows:
        if r.get('evidence_id') == 'target_box_b-8ede22c0':
            r['box_rise_m'] = 0.055   # inside the success band
    write_jsonl(root / 'stage_pick.jsonl', rows)


@case
def j_carry_identity_added_rejected(root):
    raw = (root / 'stage_carry.jsonl').read_bytes().split(b'\n')
    for index, line in enumerate(raw):
        if b'"event": "stop"' in line:
            raw[index] = line.replace(b'"event": "stop"',
                                      b'"event": "stop", "request_id": "forged"')
            break
    (root / 'stage_carry.jsonl').write_bytes(b'\n'.join(raw))


@case
def k_extra_trial_rejected(root):
    rows = read_jsonl(root / 'A.jsonl')
    extra = dict(rows[-1])
    extra['trial'] = 6
    rows.append(extra)
    write_jsonl(root / 'A.jsonl', rows)


@case
def l_probe_rise_mismatch_rejected(root):
    rows = read_jsonl(root / 'A.jsonl')
    rows[1]['rise_m'] = rows[1]['rise_m'] + 0.01   # poses no longer support it
    write_jsonl(root / 'A.jsonl', rows)


@case
def m_attach_gap_outside_radius_rejected(root):
    rows = read_jsonl(root / 'stage_pick.jsonl')
    for r in rows:
        if r.get('evidence_id') == 'target_box_b-219f0ce8':
            r['attach_gap_m'] = 0.31
    write_jsonl(root / 'stage_pick.jsonl', rows)


def main():
    failures = 0
    for fn in CASES:
        tmp, root = scratch()
        try:
            fn(root)
            rc, out = run(root)
            expected = 0 if fn.__name__.startswith('a_') else 1
            verdict = 'PASS' if rc == expected else 'FAIL'
            if rc != expected:
                failures += 1
                tail = [l for l in out.splitlines() if 'FAIL' in l][:3]
                detail = ' | '.join(tail) if tail else out.splitlines()[-1:][0] if out else ''
            else:
                detail = ''
            print('%-42s %s  (expected exit %d, got %d)%s'
                  % (fn.__name__, verdict, expected, rc,
                     ('  ' + detail) if detail else ''))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print()
    total = len(CASES)
    print('%d/%d cases behave as declared' % (total - failures, total))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
