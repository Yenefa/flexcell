#!/usr/bin/env python3
"""Adversarial selftest for verify_phase3_window_v2.py.

Same discipline as selftest_verify_phase3_window.py: a checker that cannot fail
proves nothing. Each case copies the archive, contradicts one declared fact, and
requires the expected exit code. The first case is the positive control.

Two cases exist only for v2 and are the reason it exists:

* g_trims_the_historical_population_to_negatives — the withdrawn v1 conclusion
  ("a different population") is now enforced against the evidence. If someone
  edits the historical archive until only negative rises remain, v2 fails
  instead of agreeing.
* h_lifts_the_window_failure_above_the_historical_support — if a future archive
  really does sit outside the historical range, v2 fails and a human has to
  re-narrate the window rather than inherit this text.

Run:  python3 selftest_verify_phase3_window_v2.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, 'verify_phase3_window_v2.py')
HIST = os.path.join(os.path.dirname(HERE), 'grasp_b001_20261025')

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def copy_archive(tmp):
    dst = os.path.join(tmp, 'archive')
    shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns('__pycache__'))
    return dst


def copy_hist(tmp):
    dst = os.path.join(tmp, 'hist')
    os.makedirs(dst)
    shutil.copyfile(os.path.join(HIST, 'stage_pick.jsonl'),
                    os.path.join(dst, 'stage_pick.jsonl'))
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


@case
def a_untouched_archive_still_passes(root, hist):
    return 0


@case
def b_the_failure_relabelled_as_success(root, hist):
    def edit(rows):
        for row in rows:
            if not row.get('pick_ok'):
                row['pick_ok'] = True
                row['error_code'] = 0
        return rows
    rewrite(os.path.join(root, 'B5.jsonl'), edit)
    return 1


@case
def c_a_missing_lookup_hidden_in_every_summary(root, hist):
    def edit(rows):
        for row in rows:
            if row.get('event') == 'teleport_loop_summary':
                row['ee_missing_count'] = 9
        return rows
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def c2_only_the_last_summary_per_session_altered(root, hist):
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
def c3_a_non_final_record_pushed_to_the_end(root, hist):
    def edit(rows):
        summaries = [r for r in rows if r.get('event') == 'teleport_loop_summary']
        others = [r for r in rows if r.get('event') != 'teleport_loop_summary']
        return others + [r for r in summaries if not r.get('final')]
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def d_extra_pin_failures_added(root, hist):
    def edit(rows):
        for row in rows:
            if row.get('event') == 'teleport_loop_summary':
                row['pin_failed'] = 6
        return rows
    rewrite(os.path.join(root, 'logs', 'carry_window.jsonl'), edit)
    return 1


@case
def e_the_final_summary_dropped(root, hist):
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
def f_the_failure_moved_into_the_historical_shape(root, hist):
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


@case
def g_trims_the_historical_population_to_negatives(root, hist):
    """v1 would still pass; v2 must not."""
    def edit(rows):
        kept = []
        for row in rows:
            natural = (not row.get('injected')
                       and not str(row.get('detail', '')).startswith('injected failure')
                       and str(row.get('error_code')) == '23'
                       and 'box_rise_m' in row)
            if natural and row['box_rise_m'] < 0:
                kept.append(row)
            elif not natural:
                kept.append(row)
        return kept
    rewrite(os.path.join(hist, 'stage_pick.jsonl'), edit)
    return 1


@case
def h_lifts_the_window_failure_above_the_historical_support(root, hist):
    def edit(rows):
        for row in rows:
            if row.get('object_name') == 'target_box_b' and not row.get('pick_ok'):
                row['rise_m'] = 0.0305
                row['after'] = [row['before'][0], row['before'][1],
                                row['before'][2] + 0.0305]
        return rows
    rewrite(os.path.join(root, 'B5.jsonl'), edit)

    def edit_picks(rows):
        for row in rows:
            if str(row.get('error_code')) == '23':
                row['box_rise_m'] = 0.0305
                row['box_after'] = [row['box_before'][0], row['box_before'][1],
                                    row['box_before'][2] + 0.0305]
        return rows
    rewrite(os.path.join(root, 'logs', 'pick_window.jsonl'), edit_picks)
    return 1


def run(root, hist):
    proc = subprocess.run([sys.executable, VERIFY, root, hist],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    bad = 0
    for fn in CASES:
        tmp = tempfile.mkdtemp(prefix='p3_v2_selftest_')
        try:
            root = copy_archive(tmp)
            hist = copy_hist(tmp)
            expected = fn(root, hist)
            got, out = run(root, hist)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = got == expected
        print('%-56s %s  expected=%d got=%d'
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
