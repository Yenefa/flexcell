#!/usr/bin/env python3
"""Read-only timeline: pose observations annotated with the action phase around them.

WHY THIS EXISTS
    Action phases and world-state observations arrive on different channels with
    different clocks: a phase record carries the simulator/ROS stamp of when the
    action switched, an observation carries the stamp of when the state was
    sampled, and each is received on the host at some third moment. Archiving
    them as two JSONL files makes every later question ("which phase was this
    sample in?") depend on whoever re-derives it.

    This tool derives it once, and writes down exactly how much it does not know.
    It never interpolates a pose, never resamples a stream and never invents a
    boundary timestamp; it reports the raw sampling interval and the age of the
    phase record that governs each sample, so a reader can see the resolution
    limit instead of trusting a fabricated one.

DUPLICATE SNAPSHOTS ARE NOT MEASUREMENTS
    The world-state recorder can deliver the same snapshot twice: once from the
    topic subscription and once from an action result. Those copies share a
    source stamp AND a pose, so they are marked dup_of=<first row> and excluded
    from every count. Two samples that share a stamp but disagree on the pose are
    a different thing - a conflicting measurement - and are marked
    DUPLICATE_SOURCE_STAMP instead. Neither is silently dropped: both stay in the
    CSV, only out of the totals.

WHAT THIS IS NOT
    A time window in which two things happened is not evidence that one caused
    the other, and no phase boundary here is a contact or physics acceptance
    claim. The summary states both negations as data (causality_claim=false,
    independent_acceptance_claim=false) so it cannot be quoted as one.

READ-ONLY
    Both inputs are hashed before and after the write; the only writes go to a
    freshly created output directory which is never an existing directory.

Usage:
  python scripts/pose_stage_timeline.py RUN --out NEW_DIR
  python scripts/pose_stage_timeline.py RUN --observations A.jsonl --phases B.jsonl --out NEW_DIR
  python scripts/pose_stage_timeline.py RUN          # --out defaults to RUN-timeline-<utc>

Exit codes: 0 when the timeline was written (unalignable rows are output, not a
failure), 2 when the input cannot be read as a timeline at all.
"""
import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

KIND = 'POSE_STAGE_TIMELINE'
OBSERVATION_CANDIDATES = ('observations.jsonl', 'world_state.jsonl', 'poses.jsonl',
                          'data/observations.jsonl')
PHASE_CANDIDATES = ('phases.jsonl', 'stages.jsonl', 'action_phases.jsonl',
                    'data/phases.jsonl')
SOURCE_STAMP_KEYS = ('source_stamp_ns', 'stamp_ns', 'header_stamp_ns', 'sim_ns')
RECV_STAMP_KEYS = ('recv_stamp_ns', 'observed_monotonic_ns', 'rx_mono_ns', 'monotonic_ns',
                   'recv_ns')
PHASE_NAME_KEYS = ('phase', 'stage', 'name')
PRIORITY = ('MISSING_SOURCE_STAMP', 'NON_FINITE_POSE', 'MISSING_POSE', 'DUPLICATE_COPY',
            'DUPLICATE_SOURCE_STAMP', 'OUT_OF_ORDER', 'CLOCK_ROLLBACK', 'NO_PHASE_YET')
CSV_COLUMNS = ('index', 'phase', 'source_stamp_ns', 'recv_stamp_ns', 'offset_ms',
               'x', 'y', 'z', 'delta_from_prev', 'dup_of', 'interval_ns', 'freshness_s',
               'alignable', 'reason')


class TimelineError(Exception):
    """Input that cannot be read as a timeline; always surfaces as a non-zero exit."""


def fail(message):
    raise TimelineError(message)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite(value):
    return number(value) and math.isfinite(value)


def cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else ''
    return value


def resolve(run, name, candidates, label):
    if name is not None:
        path = Path(name)
        if not path.is_absolute():
            path = run / path
        if not path.is_file():
            fail('%s file does not exist: %s' % (label, path))
        return path
    for relative in candidates:
        path = run / relative
        if path.is_file():
            return path
    fail('no %s file under %s; looked for %s' % (label, run, ', '.join(candidates)))


def read_jsonl(path):
    rows = []
    for number_, text in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), start=1):
        if not text.strip():
            continue
        try:
            value = json.loads(text)
        except ValueError as exc:
            fail('%s line %d is not JSON: %s' % (path, number_, exc))
        if not isinstance(value, dict):
            fail('%s line %d is not a JSON object' % (path, number_))
        rows.append((number_, value))
    return rows


def stamp_of(row, keys):
    """Integer nanosecond stamp, or None when absent/not an exact integer."""
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None
    return None


def pose_of(row):
    """(x, y, z, reason); z is None when the sample carries only a plane."""
    for key in ('pose', 'position'):
        if key in row:
            return pose_xyz(row[key])
    if 'x' in row or 'y' in row or 'z' in row:
        return pose_xyz([row.get('x'), row.get('y'), row.get('z')])
    return None, None, None, 'MISSING_POSE'


def pose_xyz(value):
    if isinstance(value, dict):
        if 'position' in value:
            return pose_xyz(value['position'])
        if any(key in value for key in ('x', 'y', 'z')):
            return pose_xyz([value.get('x'), value.get('y'), value.get('z')])
        return None, None, None, 'MISSING_POSE'
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        parts = list(value) + [None] * (3 - len(value))
        if parts[0] is None or parts[1] is None:
            return None, None, None, 'MISSING_POSE'
        if not all(finite(v) for v in parts if v is not None):
            return None, None, None, 'NON_FINITE_POSE'
        return float(parts[0]), float(parts[1]), (
            None if parts[2] is None else float(parts[2])), None
    return None, None, None, 'MISSING_POSE'


def distance(a, b):
    """Distance over the coordinates both samples carry; never invents z."""
    if a[2] is None or b[2] is None:
        return math.hypot(a[0] - b[0], a[1] - b[1])
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def phase_records(rows):
    records = []
    for line, row in rows:
        name = None
        for key in PHASE_NAME_KEYS:
            if key in row:
                name = row[key]
                break
        if not isinstance(name, str) or not name.strip():
            fail('phase row %d has no usable phase/stage name' % line)
        stamp = stamp_of(row, SOURCE_STAMP_KEYS)
        if stamp is None:
            fail('phase row %d has no integer source stamp' % line)
        recv = stamp_of(row, RECV_STAMP_KEYS)
        records.append(dict(line=line, phase=name.strip(), source_stamp_ns=stamp,
                            recv_stamp_ns=recv, index=len(records) + 1))
    if not records:
        fail('the phase file has no records; without phases nothing can be aligned')
    records.sort(key=lambda record: (record['source_stamp_ns'], record['index']))
    return records


def assign_phase(stamps, phases, stamp):
    """Last phase record at or before the sample: causal, never interpolated."""
    position = bisect.bisect_right(stamps, stamp) - 1
    return None if position < 0 else phases[position]


def build(rows, phases):
    stamps = [record['source_stamp_ns'] for record in phases]
    snapshots = {}
    stamped = {}
    timeline = []
    previous_stamp = previous_recv = last_counted = None
    for index, (line, row) in enumerate(rows, start=1):
        source = stamp_of(row, SOURCE_STAMP_KEYS)
        recv = stamp_of(row, RECV_STAMP_KEYS)
        x, y, z, pose_reason = pose_of(row)
        reasons = []
        offset_ms = ((recv - source) / 1e6) if source is not None and recv is not None else None
        interval = None
        if source is not None and previous_stamp is not None:
            interval = source - previous_stamp
        if source is not None:
            previous_stamp = source

        rollback = recv is not None and previous_recv is not None and recv < previous_recv
        if recv is not None:
            previous_recv = recv

        if source is None:
            reasons.append('MISSING_SOURCE_STAMP')
        if pose_reason is not None:
            reasons.append(pose_reason)
        dup_of = None
        if not reasons:
            key = (source, x, y, z)
            if key in snapshots:
                dup_of = snapshots[key]
                reasons.append('DUPLICATE_COPY')
            elif source in stamped:
                reasons.append('DUPLICATE_SOURCE_STAMP')
            else:
                snapshots[key] = index
                stamped[source] = index
                if last_counted is not None and source < last_counted['source_stamp_ns']:
                    reasons.append('OUT_OF_ORDER')
        if rollback:
            reasons.append('CLOCK_ROLLBACK')

        phase = age = None
        if not reasons:
            record = assign_phase(stamps, phases, source)
            if record is None:
                reasons.append('NO_PHASE_YET')
            else:
                phase = record['phase']
                age = (source - record['source_stamp_ns']) / 1e9

        entry = dict(index=index, line=line, phase=phase, source_stamp_ns=source,
                     recv_stamp_ns=recv, offset_ms=offset_ms, x=x, y=y, z=z,
                     delta_from_prev=None, dup_of=dup_of, interval_ns=interval,
                     freshness_s=age, alignable=not reasons,
                     reason=None if not reasons else [r for r in PRIORITY if r in reasons][0])
        if entry['alignable'] and last_counted is not None:
            entry['delta_from_prev'] = distance(
                (last_counted['x'], last_counted['y'], last_counted['z']), (x, y, z))
        if entry['alignable']:
            last_counted = entry
        timeline.append(entry)
    return timeline


def stage_summary(timeline, phases):
    counted = [entry for entry in timeline if entry['alignable']]
    reasons = {}
    for entry in timeline:
        if entry['reason'] is not None:
            reasons[entry['reason']] = reasons.get(entry['reason'], 0) + 1
    intervals = [entry['interval_ns'] for entry in counted
                 if entry['interval_ns'] is not None and entry['interval_ns'] > 0]
    offsets = [entry['offset_ms'] for entry in timeline if entry['offset_ms'] is not None]
    freshness = [entry['freshness_s'] for entry in counted if entry['freshness_s'] is not None]
    grouped = {}
    for entry in counted:
        bucket = grouped.setdefault(entry['phase'], dict(rows=0, first_source_stamp_ns=None,
                                                        last_source_stamp_ns=None))
        bucket['rows'] += 1
        if bucket['first_source_stamp_ns'] is None:
            bucket['first_source_stamp_ns'] = entry['source_stamp_ns']
        bucket['last_source_stamp_ns'] = entry['source_stamp_ns']
    boundaries = []
    counted_stamps = [entry['source_stamp_ns'] for entry in counted]
    for record in phases:
        boundary = record['source_stamp_ns']
        position = bisect.bisect_left(counted_stamps, boundary)
        before = counted[position - 1] if position > 0 else None
        after = counted[position] if position < len(counted) else None
        window = None
        if before is not None and after is not None:
            window = after['source_stamp_ns'] - before['source_stamp_ns']
        boundaries.append(dict(
            phase=record['phase'], source_stamp_ns=boundary,
            recv_stamp_ns=record['recv_stamp_ns'],
            offset_ms=((record['recv_stamp_ns'] - boundary) / 1e6)
            if record['recv_stamp_ns'] is not None else None,
            last_sample_before=before['index'] if before else None,
            first_sample_after=after['index'] if after else None,
            window_ns=window, bounded=window is not None))
    return dict(
        rows_total=len(timeline), rows_counted=len(counted),
        rows_unalignable=len(timeline) - len(counted), reasons=reasons,
        duplicates=dict(copies=sum(1 for e in timeline if e['dup_of'] is not None),
                        conflicting_stamps=reasons.get('DUPLICATE_SOURCE_STAMP', 0)),
        phases=grouped,
        phase_records=[dict(index=r['index'], phase=r['phase'],
                            source_stamp_ns=r['source_stamp_ns'],
                            recv_stamp_ns=r['recv_stamp_ns']) for r in phases],
        phase_boundaries=boundaries,
        sampling=dict(
            counted=len(intervals),
            intervals_ns=dict(min=min(intervals), median=statistics.median(intervals),
                              max=max(intervals)) if intervals else None,
            span_ns=(counted[-1]['source_stamp_ns'] - counted[0]['source_stamp_ns'])
            if len(counted) > 1 else 0,
            duplicate_intervals=sum(1 for e in timeline if e['interval_ns'] == 0
                                    and e['dup_of'] is None)),
        offset_ms=dict(min=min(offsets), max=max(offsets),
                       negative=sum(1 for value in offsets if value < 0)) if offsets else None,
        freshness_s=dict(min=min(freshness), max=max(freshness)) if freshness else None)


def write_csv(path, timeline):
    with Path(path).open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(CSV_COLUMNS)
        for entry in timeline:
            writer.writerow([cell(entry[column]) for column in CSV_COLUMNS])


def choose_out(run, requested):
    if requested is not None:
        out = Path(requested)
        if out.exists():
            fail('output directory already exists: %s (a new directory per run, never in place)'
                 % out)
        out.mkdir(parents=True)
        return out
    stem = run.name or 'run'
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    for suffix in [''] + ['-%02d' % n for n in range(1, 100)]:
        out = run.parent / ('%s-timeline-%s%s' % (stem, stamp, suffix))
        try:
            out.mkdir()
            return out
        except FileExistsError:
            continue
    fail('cannot create a fresh output directory next to %s' % run)


def timeline(run, observations, phases_path, out_dir):
    run = Path(run).resolve()
    if not run.is_dir():
        fail('run directory does not exist: %s' % run)
    observations_path = resolve(run, observations, OBSERVATION_CANDIDATES, 'observations')
    phases_file = resolve(run, phases_path, PHASE_CANDIDATES, 'phases')
    before = {str(path): sha256_file(path) for path in (observations_path, phases_file)}
    rows = read_jsonl(observations_path)
    if not rows:
        fail('%s has no rows; an empty timeline is not a timeline' % observations_path)
    phases = phase_records(read_jsonl(phases_file))
    entries = build(rows, phases)
    if not any(entry['source_stamp_ns'] is not None for entry in entries):
        fail('no observation row carries an integer source stamp (%s); this does not look '
             'like an observation stream' % ', '.join(SOURCE_STAMP_KEYS))
    summary = dict(
        kind=KIND, run_dir=str(run), out_dir=str(out_dir),
        observations_path=str(observations_path), phases_path=str(phases_file),
        columns=list(CSV_COLUMNS),
        inputs=[dict(path=str(path), sha256=before[str(path)], bytes=path.stat().st_size,
                     rows=len(read_jsonl(path))) for path in (observations_path, phases_file)],
        generated_utc_ns=time.time_ns(), **stage_summary(entries, phases))
    summary.update(
        # Stated as data so the file cannot be quoted as something it is not.
        interpolation='none', resampling='none', row_creation='none',
        causality_claim=False, independent_acceptance_claim=False,
        definitions=dict(
            phase='last phase record at or before the sample source stamp; never interpolated',
            source_stamp_ns='stamp carried by the sample itself (simulator/ROS clock)',
            recv_stamp_ns='host receipt stamp; a different clock domain from the source',
            offset_ms='recv_stamp_ns - source_stamp_ns, raw; not a latency claim across clocks',
            delta_from_prev='distance from the previous counted sample, over shared coordinates',
            interval_ns='source-stamp difference to the previous row in file order, raw and '
                        'possibly negative or zero; never clamped or resampled',
            freshness_s='source-clock age of the phase record governing this sample, i.e. how '
                        'precisely the boundary is known without interpolation'),
        notes=['a shared time window is not contact causality',
               'phase alignment bounds are reported as window_ns, not tightened'])
    write_csv(out_dir / 'timeline.csv', entries)
    changed = [path for path in (observations_path, phases_file)
               if sha256_file(path) != before[str(path)]]
    summary['inputs_unchanged'] = not changed
    with (out_dir / 'summary.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
        stream.write('\n')
    if changed:
        fail('input changed while building the timeline: %s' % ', '.join(str(p) for p in changed))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='run directory holding the JSONL inputs')
    parser.add_argument('--out', type=Path,
                        help='new output directory (must not exist); defaults to RUN-timeline-<utc>')
    parser.add_argument('--observations', help='observation JSONL, absolute or run-relative')
    parser.add_argument('--phases', help='phase JSONL, absolute or run-relative')
    args = parser.parse_args(argv)
    try:
        out_dir = choose_out(args.run.resolve(), args.out)
        summary = timeline(args.run, args.observations, args.phases, out_dir)
    except TimelineError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 2
    print(json.dumps(dict(kind=summary['kind'], rows_total=summary['rows_total'],
                          rows_counted=summary['rows_counted'],
                          rows_unalignable=summary['rows_unalignable'],
                          out=str(out_dir)), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
