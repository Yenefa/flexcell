#!/usr/bin/env python3
"""Aggregate one or more four-slot pick/place windows.

Answers three questions from artifacts only:
  1. Is the commanded release pose identical across runs?
  2. Is the placement error already present at release (place drop == verify)?
  3. What is the spread of the completed normal slots?

Usage:
  python3 analyze_windows.py WINDOW_DIR [WINDOW_DIR ...] [--out analysis.json]
"""
import argparse
import json
import pathlib
import statistics

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


def slot_row(window_dir, label):
    for run in sorted(pathlib.Path(window_dir).glob(label + '/run-*')):
        result = read_json(run / 'result.json')
        if result is None:
            continue
        task = result.get('task') or {}
        place = read_jsonl(run / 'skills/place.jsonl')
        verify = read_jsonl(run / 'skills/verify.jsonl')
        mtp = read_jsonl(run / 'skills/move_to_pose.jsonl')
        targets = []
        for row in mtp:
            pos = (row.get('target') or {}).get('position')
            if pos:
                targets.append(tuple(round(float(v), 6) for v in pos))
        return dict(
            window=str(window_dir),
            label=label,
            harness_status=result.get('status'),
            outcome=task.get('outcome'),
            error_code=task.get('error_code'),
            wall_seconds=task.get('wall_seconds'),
            final_error_mm=(task.get('final_position_error_m') or 0) * 1000
            if task.get('final_position_error_m') is not None else None,
            place_drop_mm=parse_mm(place[-1].get('detail'), 'drop error') if place else None,
            verify_error_mm=parse_mm(verify[-1].get('detail'), 'err=') if verify else None,
            last_targets=targets[-2:],
        )
    return dict(window=str(window_dir), label=label, missing=True)


def summarize(rows):
    completed = [r for r in rows if not r.get('missing') and r.get('final_error_mm') is not None]
    errors = [r['final_error_mm'] for r in completed]
    deltas = [abs((r['place_drop_mm'] or 0) - (r['verify_error_mm'] or 0)) for r in completed]
    targets = [tuple(r['last_targets']) for r in completed if r.get('last_targets')]
    unique_targets = sorted({t for t in targets})
    return dict(
        slots_attempted=len(rows),
        slots_completed=len(completed),
        unknown=sum(1 for r in rows if r.get('harness_status') == 'ACTION_TERMINAL_UNKNOWN'),
        error_mm=dict(
            n=len(errors),
            mean=round(statistics.mean(errors), 2) if errors else None,
            stdev=round(statistics.stdev(errors), 2) if len(errors) > 1 else None,
            min=round(min(errors), 2) if errors else None,
            max=round(max(errors), 2) if errors else None,
            spread=round(max(errors) - min(errors), 2) if errors else None,
        ),
        max_place_verify_delta_mm=round(max(deltas), 3) if deltas else None,
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
