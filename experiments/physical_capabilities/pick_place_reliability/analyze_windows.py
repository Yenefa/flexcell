#!/usr/bin/env python3
"""Aggregate one or more four-slot pick/place windows.

Answers three questions from artifacts only:
  1. Is the commanded release pose identical across runs?
  2. Is the placement error already present at the first post-release sample?
  3. What is the spread of the completed normal slots?

Only slots that pass every validity check enter the error statistics. Failed,
unknown, ambiguous, unreadable and unmeasured slots are reported with their own
status and reason instead of being turned into a zero error, and two run
directories for one slot are reported as ambiguous rather than silently reduced
to the first one.

Usage:
  python3 analyze_windows.py WINDOW_DIR [WINDOW_DIR ...] [--out analysis.json]
"""
import argparse
import json
import pathlib
import statistics

import run_window

NORMAL_LABELS = ('NORMAL_1', 'NORMAL_2')


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def read_jsonl(path):
    p = pathlib.Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def parse_mm(detail, marker):
    """Extract a metre value from a skill detail string, return mm or None."""
    if not isinstance(detail, str) or marker not in detail:
        return None
    tail = detail.split(marker, 1)[1]
    number = ''
    for ch in tail.strip():
        if ch.isdigit() or ch in '.-':
            number += ch
        else:
            break
    try:
        return float(number) * 1000.0
    except ValueError:
        return None


def run_directories(window_dir, label):
    return sorted(p for p in pathlib.Path(window_dir).glob(label + '/run-*') if p.is_dir())


def slot_status(runs, result):
    """A slot is OK only when it has one run directory, a result, and a clean PASS."""
    if not runs:
        return 'MISSING', 'no run-* directory'
    if len(runs) > 1:
        return 'AMBIGUOUS', '%d run-* directories: %s' % (
            len(runs), ', '.join(p.name for p in runs))
    if result is None:
        return 'NO_RESULT', 'result.json missing or unreadable'
    if run_window.unknown(result):
        return 'UNKNOWN', 'unknown terminal state in result'
    if result.get('status') != 'PASS':
        return 'TASK_FAILED', 'harness status %r' % result.get('status')
    outcome = (result.get('task') or {}).get('outcome')
    if outcome not in (None, 'OUTCOME_SUCCEEDED'):
        return 'TASK_FAILED', 'task outcome %r' % outcome
    return 'OK', None


def slot_row(window_dir, label):
    runs = run_directories(window_dir, label)
    result = read_json(runs[0] / 'result.json') if len(runs) == 1 else None
    status, reason = slot_status(runs, result)

    row = dict(window=str(window_dir), label=label, status=status)
    if reason:
        row['reason'] = reason
    if len(runs) == 1:
        row['run_dir'] = runs[0].name
    if result is None:
        return row

    task = result.get('task') or {}
    place = read_jsonl(runs[0] / 'skills/place.jsonl')
    verify = read_jsonl(runs[0] / 'skills/verify.jsonl')
    mtp = read_jsonl(runs[0] / 'skills/move_to_pose.jsonl')
    targets = []
    for item in mtp:
        pos = (item.get('target') or {}).get('position')
        if pos:
            targets.append(tuple(round(float(v), 6) for v in pos))

    measured = task.get('final_position_error_m')
    row.update(
        harness_status=result.get('status'),
        outcome=task.get('outcome'),
        error_code=task.get('error_code'),
        wall_seconds=task.get('wall_seconds'),
        final_error_mm=float(measured) * 1000.0 if isinstance(measured, (int, float)) else None,
        place_drop_mm=parse_mm(place[-1].get('detail'), 'drop error') if place else None,
        verify_error_mm=parse_mm(verify[-1].get('detail'), 'err=') if verify else None,
        last_targets=targets[-2:],
    )
    return row


def summarize(rows):
    valid = [r for r in rows
             if r.get('status') == 'OK' and r.get('final_error_mm') is not None]
    valid_ids = {id(r) for r in valid}
    errors = [r['final_error_mm'] for r in valid]
    deltas = [abs(r['place_drop_mm'] - r['verify_error_mm']) for r in valid
              if r.get('place_drop_mm') is not None
              and r.get('verify_error_mm') is not None]
    targets = [tuple(r['last_targets']) for r in valid if r.get('last_targets')]
    unique_targets = sorted({t for t in targets})

    def count(status):
        return sum(1 for r in rows if r.get('status') == status)

    excluded = []
    for row in rows:
        if id(row) in valid_ids:
            continue
        reason = row.get('reason')
        if reason is None and row.get('status') == 'OK':
            reason = 'no final_position_error_m'
        excluded.append(dict(label=row.get('label'), window=row.get('window'),
                             status=row.get('status'), reason=reason))

    return dict(
        slots_attempted=len(rows),
        slots_completed=len(valid),
        slots_task_failed=count('TASK_FAILED'),
        slots_unknown=count('UNKNOWN'),
        slots_missing=count('MISSING'),
        slots_ambiguous=count('AMBIGUOUS'),
        slots_no_result=count('NO_RESULT'),
        slots_unmeasured=sum(1 for r in rows if r.get('status') == 'OK'
                             and r.get('final_error_mm') is None),
        excluded=excluded,
        error_mm=dict(
            n=len(errors),
            mean=round(statistics.mean(errors), 2) if errors else None,
            stdev=round(statistics.stdev(errors), 2) if len(errors) > 1 else None,
            min=round(min(errors), 2) if errors else None,
            max=round(max(errors), 2) if errors else None,
            spread=round(max(errors) - min(errors), 2) if errors else None,
        ),
        max_place_verify_delta_mm=round(max(deltas), 3) if deltas else None,
        place_verify_delta_mm=dict(
            n=len(deltas),
            max=round(max(deltas), 3) if deltas else None,
        ),
        unique_release_target_sets=len(unique_targets),
        release_targets=[[list(v) for v in t] for t in unique_targets],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('windows', nargs='+')
    parser.add_argument('--out', type=pathlib.Path)
    args = parser.parse_args(argv)

    rows = []
    for window in args.windows:
        for label in NORMAL_LABELS:
            rows.append(slot_row(window, label))

    summary = summarize(rows)
    payload = dict(rows=rows, summary=summary)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + '\n')
    print(text)
    return 0 if summary['slots_completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
