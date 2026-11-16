#!/usr/bin/env python3
"""Aggregate one or more four-slot pick/place windows.

Answers three questions from artifacts only:
  1. Is the commanded release pose identical across runs?
  2. Is the placement error already present at the first post-release sample?
  3. What is the spread of the completed normal slots?

Only slots that pass every validity check enter the error statistics. The window
driver's own verdict is checked first, so a slot the driver marked UNKNOWN
(outer timeout, stop after an unknown terminal state) cannot come back as OK just
because a raw PASS result survived on disk. Failed, unknown, interrupted,
ambiguous, unreadable and unmeasured slots are reported with their own status and
reason instead of being turned into a zero error, two run directories for one
slot are reported as ambiguous, and a truncated JSONL line is recorded against
its slot without aborting the other windows.

Usage:
  python3 analyze_windows.py WINDOW_DIR [WINDOW_DIR ...] [--out analysis.json]
"""
import argparse
import json
import math
import pathlib
import statistics

import run_window

NORMAL_LABELS = ('NORMAL_1', 'NORMAL_2')


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def finite_number(value):
    """True only for a real, finite number; bool and NaN/Inf are rejected."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (TypeError, OverflowError):
        return False


def read_jsonl(path):
    """Return (records, errors); a damaged line is isolated to its own slot.

    A run stopped mid-write can leave a truncated last line. Aborting the whole
    analysis would hide every other usable window, so malformed lines become
    per-slot evidence and the remaining lines are still read.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return [], []
    try:
        text = p.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        return [], [dict(file=p.name, error='unreadable: %s' % exc)]
    records, errors = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError as exc:
            errors.append(dict(file=p.name, line=number, error='invalid JSON: %s' % exc))
            continue
        if not isinstance(value, dict):
            errors.append(dict(file=p.name, line=number, error='not a JSON object'))
            continue
        records.append(value)
    return records, errors


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
        value = float(number) * 1000.0
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def run_directories(window_dir, label):
    return sorted(p for p in pathlib.Path(window_dir).glob(label + '/run-*') if p.is_dir())


def window_driver_rows(window_dir):
    """Read the window driver's own verdict; return (rows_by_label, error)."""
    data = read_json(pathlib.Path(window_dir) / 'results.json')
    if not isinstance(data, dict):
        return None, 'window results.json missing or unreadable'
    rows = data.get('results')
    if not isinstance(rows, list):
        return None, 'window results.json has no results list'
    drivers = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('label'), str):
            label = row['label']
            if label in drivers:
                return None, 'window results.json has duplicate rows for %r' % label
            drivers[label] = row
    if not drivers:
        return None, 'window results.json has no usable rows'
    return drivers, None


def slot_status(runs, result, driver=None, metadata_error=None):
    """A slot is OK only when the driver and the raw result both agree.

    The raw `result.json` cannot see why the window stopped. If the outer
    timeout killed the slot after a PASS result was written, the driver says
    UNKNOWN and that verdict wins. Unreadable window metadata stays UNKNOWN
    instead of being treated as a clean run.
    """
    if len(runs) > 1:
        return 'AMBIGUOUS', '%d run-* directories: %s' % (
            len(runs), ', '.join(p.name for p in runs))
    if driver is not None and driver.get('status') != 'OK':
        mapped = {'UNKNOWN': 'UNKNOWN', 'TASK_FAILED': 'TASK_FAILED',
                  'NOT_RUN': 'NOT_RUN', 'INTERRUPTED': 'INTERRUPTED'}
        return mapped.get(driver.get('status'), 'UNKNOWN'), \
            'window driver status %r' % driver.get('status')
    if driver is not None:
        driver_exit = driver.get('driver_exit')
        if driver_exit is not None and driver_exit != 0:
            return 'UNKNOWN', 'driver status OK but driver_exit is %r' % driver_exit
    if not runs:
        return 'MISSING', 'no run-* directory'
    if metadata_error:
        return 'UNKNOWN', metadata_error
    if driver is None:
        return 'UNKNOWN', 'no driver row for this slot'
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


def slot_row(window_dir, label, drivers=None, metadata_error=None):
    if drivers is None and metadata_error is None:
        drivers, metadata_error = window_driver_rows(window_dir)
    runs = run_directories(window_dir, label)
    result = read_json(runs[0] / 'result.json') if len(runs) == 1 else None
    status, reason = slot_status(runs, result, drivers.get(label) if drivers else None,
                                 metadata_error)
    driver = drivers.get(label) if drivers else None

    row = dict(window=str(window_dir), label=label, status=status)
    if reason:
        row['reason'] = reason
    if metadata_error:
        row['metadata_error'] = metadata_error
    if driver is not None:
        row['driver_status'] = driver.get('status')
        row['driver_exit'] = driver.get('driver_exit')
    if len(runs) == 1:
        row['run_dir'] = runs[0].name
    if result is None:
        return row

    task = result.get('task') or {}
    place, place_errors = read_jsonl(runs[0] / 'skills/place.jsonl')
    verify, verify_errors = read_jsonl(runs[0] / 'skills/verify.jsonl')
    mtp, mtp_errors = read_jsonl(runs[0] / 'skills/move_to_pose.jsonl')
    log_errors = place_errors + verify_errors + mtp_errors
    targets = []
    for item in mtp:
        target = item.get('target')
        if not isinstance(target, dict):
            continue
        pos = target.get('position')
        if not isinstance(pos, (list, tuple)) or len(pos) != 3:
            continue
        try:
            values = [float(v) for v in pos]
        except (TypeError, ValueError, OverflowError):
            log_errors.append(dict(file='move_to_pose.jsonl',
                                   error='invalid target position %r' % (pos,)))
            continue
        if not all(math.isfinite(v) for v in values):
            log_errors.append(dict(file='move_to_pose.jsonl',
                                   error='non-finite target position %r' % (pos,)))
            continue
        targets.append(tuple(round(v, 6) for v in values))

    measured = task.get('final_position_error_m')
    row.update(
        harness_status=result.get('status'),
        outcome=task.get('outcome'),
        error_code=task.get('error_code'),
        wall_seconds=task.get('wall_seconds'),
        final_error_mm=(float(measured) * 1000.0
                        if finite_number(measured) else None),
        place_drop_mm=(parse_mm(place[-1].get('detail'), 'drop error')
                       if place and not place_errors else None),
        verify_error_mm=(parse_mm(verify[-1].get('detail'), 'err=')
                         if verify and not verify_errors else None),
        last_targets=[] if mtp_errors else targets[-2:],
    )
    if log_errors:
        row['log_errors'] = log_errors
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
        slots_interrupted=count('INTERRUPTED'),
        slots_not_run=count('NOT_RUN'),
        slots_missing=count('MISSING'),
        slots_ambiguous=count('AMBIGUOUS'),
        slots_no_result=count('NO_RESULT'),
        slots_metadata_missing=sum(1 for r in rows if r.get('metadata_error')),
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
    windows = []
    for window in args.windows:
        drivers, metadata_error = window_driver_rows(window)
        meta = read_json(pathlib.Path(window) / 'results.json')
        windows.append(dict(
            window=str(window),
            metadata_error=metadata_error,
            stop_reason=meta.get('stop_reason') if isinstance(meta, dict) else None,
            all_slots_completed=(meta.get('all_slots_completed')
                                 if isinstance(meta, dict) else None),
            interrupted=(meta.get('interrupted') if isinstance(meta, dict) else None),
        ))
        for label in NORMAL_LABELS:
            rows.append(slot_row(window, label, drivers, metadata_error))

    summary = summarize(rows)
    payload = dict(windows=windows, rows=rows, summary=summary)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + '\n')
    print(text)
    return 0 if summary['slots_completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
