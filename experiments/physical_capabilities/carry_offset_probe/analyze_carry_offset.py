#!/usr/bin/env python3
"""Join carry-offset samples with the landing error of the same slot.

Reads, per slot:
  - `carry_offset.jsonl`      (written by probe.py)
  - `run-*/result.json`       (the window's own evidence)

and reports, for every carry session in the slot, the object offset in the
gripper frame at engage, at the settled `grasp` sample, at release, the change
between the baseline and release, and the slot's landing error.

`dual_object` carries two boxes in one slot, so the pairing key is the carry
session (the object name), not the slot.

Descriptive only: it does not decide whether the spread comes from grasp, carry
or tracking.

Usage:
  python3 analyze_carry_offset.py WINDOW_DIR [WINDOW_DIR ...] [--out out.json]
"""
import argparse
import json
import pathlib
import statistics

LABELS = ('NORMAL_1', 'DUAL_1', 'NORMAL_2', 'DUAL_2')
MARKERS = ('engage', 'grasp', 'release')


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def read_jsonl(path):
    p = pathlib.Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def single_run(slot):
    runs = sorted(p for p in pathlib.Path(slot).glob('run-*') if p.is_dir())
    return runs[0] if len(runs) == 1 else None


def offset_mm(row):
    if not isinstance(row, dict):
        return None
    vector = row.get('object_in_tcp')
    if not isinstance(vector, list) or len(vector) < 3:
        return None
    try:
        return [float(v) * 1000.0 for v in vector[:3]]
    except (TypeError, ValueError):
        return None


def norm_mm(vector):
    return (vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2) ** 0.5


def landing_mm(result):
    if not isinstance(result, dict):
        return None
    value = (result.get('task') or {}).get('final_position_error_m')
    if isinstance(value, (int, float)) and value == value:
        return float(value) * 1000.0
    return None


def session_rows(rows):
    """Group samples by carry session, keeping the file order."""
    order = []
    grouped = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get('carry_session') or row.get('object')
        entry = grouped.get(key)
        if entry is None:
            entry = dict(session=key, object=row.get('object'), samples=0,
                         engage=None, grasp=None, release=None, rows=[])
            grouped[key] = entry
            order.append(entry)
        entry['samples'] += 1
        entry['rows'].append(row)
        if row.get('event') in MARKERS:
            entry[row['event']] = row
    return order


def settled_sample(entry):
    """First sample whose world revision differs from the engage snapshot.

    The engage event fires while the gripper is still closing, so its offset is
    the approach pose, not the held pose. The first new revision is when the
    object starts moving with the gripper.
    """
    engage = entry['engage']
    if engage is None:
        return entry['grasp']
    revision = engage.get('world_revision')
    for row in entry['rows']:
        if row is engage:
            continue
        if row.get('world_revision') != revision:
            return row
    return entry['grasp'] or engage


def summarise_session(entry):
    engage = entry['engage']
    settled = settled_sample(entry)
    release = entry['release']
    result = dict(
        session=entry['session'],
        object=entry['object'],
        samples=entry['samples'],
        settled_event=settled.get('event') if isinstance(settled, dict) else None,
        engage_mm=offset_mm(engage),
        grasp_mm=offset_mm(entry['grasp']),
        settled_mm=offset_mm(settled),
        release_mm=offset_mm(release),
        lift_mm=None,
        lift_delta_mm=None,
        slip_mm=None,
        slip_delta_mm=None,
        delta_mm=None,
        delta_norm_mm=None,
    )
    e = result['engage_mm']
    s = result['settled_mm']
    r = result['release_mm']
    if e and s:
        result['lift_delta_mm'] = [b - a for a, b in zip(e, s)]
        result['lift_mm'] = round(norm_mm(result['lift_delta_mm']), 3)
    if s and r:
        result['slip_delta_mm'] = [b - a for a, b in zip(s, r)]
        result['slip_mm'] = round(norm_mm(result['slip_delta_mm']), 3)
    if e and r:
        result['delta_mm'] = [b - a for a, b in zip(e, r)]
        result['delta_norm_mm'] = round(norm_mm(result['delta_mm']), 3)
    return result


def slot_row(window, label):
    slot = pathlib.Path(window) / label
    rows = read_jsonl(slot / 'carry_offset.jsonl')
    skips = read_jsonl(slot / 'carry_offset_skips.jsonl')
    run = single_run(slot)
    result = read_json(run / 'result.json') if run else None

    sessions = [summarise_session(entry) for entry in session_rows(rows)]
    paired = [s for s in sessions if s['delta_norm_mm'] is not None]
    last = paired[-1] if paired else (sessions[-1] if sessions else None)

    row = dict(window=str(window), label=label,
               samples=len(rows), skips=len(skips),
               landing_mm=landing_mm(result),
               sessions=sessions,
               sessions_paired=len(paired),
               object=last['object'] if last else None,
               session=last['session'] if last else None,
               settled_event=last['settled_event'] if last else None,
               engage_mm=last['engage_mm'] if last else None,
               grasp_mm=last['grasp_mm'] if last else None,
               settled_mm=last['settled_mm'] if last else None,
               release_mm=last['release_mm'] if last else None,
               lift_mm=last['lift_mm'] if last else None,
               slip_mm=last['slip_mm'] if last else None,
               delta_mm=last['delta_mm'] if last else None,
               delta_norm_mm=last['delta_norm_mm'] if last else None)
    return row


def summarize(rows):
    sessions = [s for r in rows for s in r.get('sessions', [])]
    paired = [s for s in sessions if s.get('delta_norm_mm') is not None]
    norms = [s['delta_norm_mm'] for s in paired]
    lifts = [s['lift_mm'] for s in sessions if s.get('lift_mm') is not None]
    slips = [s['slip_mm'] for s in sessions if s.get('slip_mm') is not None]
    landings = [r['landing_mm'] for r in rows if r.get('landing_mm') is not None]

    def axis(rows_, key, index):
        values = [s[key][index] for s in rows_ if s.get(key)]
        return round(statistics.mean(values), 3) if values else None

    return dict(
        slots_attempted=len(rows),
        slots_with_probe=sum(1 for r in rows if r.get('samples')),
        slots_paired=sum(1 for r in rows if r.get('sessions_paired')),
        slots_missing=sum(1 for r in rows if not r.get('samples')),
        slots_with_skips=sum(1 for r in rows if r.get('skips')),
        sessions_total=len(sessions),
        sessions_paired=len(paired),
        lift_mm=dict(
            n=len(lifts),
            mean=round(statistics.mean(lifts), 3) if lifts else None,
            min=round(min(lifts), 3) if lifts else None,
            max=round(max(lifts), 3) if lifts else None,
        ),
        slip_mm=dict(
            n=len(slips),
            mean=round(statistics.mean(slips), 3) if slips else None,
            min=round(min(slips), 3) if slips else None,
            max=round(max(slips), 3) if slips else None,
        ),
        engage_mean_mm=[axis(paired, 'engage_mm', i) for i in range(3)],
        release_mean_mm=[axis(paired, 'release_mm', i) for i in range(3)],
        delta_norm_mm=dict(
            n=len(norms),
            mean=round(statistics.mean(norms), 3) if norms else None,
            min=round(min(norms), 3) if norms else None,
            max=round(max(norms), 3) if norms else None,
        ),
        landing_mm=dict(
            n=len(landings),
            mean=round(statistics.mean(landings), 3) if landings else None,
            min=round(min(landings), 3) if landings else None,
            max=round(max(landings), 3) if landings else None,
        ),
        note=('descriptive only; one window, no causal claim: grasp offset, '
              'carry drift and tracking error are not separated'),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('windows', nargs='+')
    parser.add_argument('--out', type=pathlib.Path)
    args = parser.parse_args(argv)

    rows = []
    for window in args.windows:
        for label in LABELS:
            rows.append(slot_row(window, label))

    summary = summarize(rows)
    payload = dict(rows=rows, summary=summary)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + '\n')
    print(text)
    return 0 if summary['sessions_paired'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
