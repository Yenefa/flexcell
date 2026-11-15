#!/usr/bin/env python3
"""Read-only audit: per-attempt reported push progress vs the run's net displacement.

WHY THESE ARE TWO NUMBERS AND NOT ONE
    "Progress" in a push archive is what each PushObject call reports as the
    object's displacement along the commanded direction; a retry policy
    accumulates those reports. "Net displacement" is where the object actually
    ended up, measured once between the endpoint poses. They diverge as soon as
    an attempt moves the object backwards: push_recover.accumulate() counts such
    an attempt as zero, never as a negative, so accumulated progress ends up
    larger than the motion that really happened. The same module's docstring
    records three of five trials "recovering" while the block travelled away
    from the goal.

    This tool puts both numbers side by side and writes the difference. It does
    not decide whether a task passed: the only conclusions here are about
    measurement, and the words pass/fail are deliberately absent from the output.

REUSED JUDGEMENT, NOT A COPY OF IT
    classify_attempt(), is_progress() and MIN_DISPLACEMENT_M are imported from
    the frozen contract module flexcell_skills.contracts.push_recover (which
    imports only math, so it is importable without ROS). The audit therefore
    cannot drift from the policy whose numbers it audits, and the per-row
    "counted" column is literally what push_recover would accumulate.

WHAT "UNKNOWN" MEANS
    A sign is only assigned when the measured projection clears
    MIN_DISPLACEMENT_M; below that floor a sign is measurement noise. Rows and
    runs that cannot support a sign keep the measured reason code instead
    (NO_MOTION, ZERO_PROJECTION, MISSING_ENDPOINT, NON_FINITE, NO_DIRECTION).
    UNKNOWN describes the evidence, not the push.

READ-ONLY
    Inputs are hashed before and after the write and the hashes are compared;
    the only writes go to a freshly created output directory, which is never an
    existing directory. Nothing is written back into the run.

Usage:
  python scripts/push_progress_audit.py RUN --out NEW_DIR [--direction dx,dy]
  python scripts/push_progress_audit.py RUN          # --out defaults to RUN-audit-<utc>

Exit codes: 0 when the audit was written (even when the result is UNKNOWN),
2 when the input cannot be audited (missing/unreadable attempts, bad direction,
existing output directory).
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / 'src' / 'flexcell' / 'flexcell_skills'
if str(SKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLS_ROOT))
try:
    from flexcell_skills.contracts.push_recover import (  # noqa: E402 - path above
        MIN_DISPLACEMENT_M, classify_attempt, is_progress)
except ImportError as exc:  # environment problem, not a data problem
    raise SystemExit('cannot import the frozen push_recover contract from %s: %s'
                     % (SKILLS_ROOT, exc))

KIND = 'PUSH_PROGRESS_AUDIT'
ATTEMPT_CANDIDATES = ('push_attempts.jsonl', 'attempts.jsonl', 'contact_push.jsonl',
                      'skills/push.jsonl', 'skills/push_object.jsonl')
BEFORE_KEYS = ('measured_before', 'pre_pose', 'start_pose', 'before_pose', 'before')
AFTER_KEYS = ('measured_after', 'post_pose', 'end_pose', 'after_pose', 'after')
ALONG_KEYS = ('displacement_along_direction_m', 'along_m')
MAGNITUDE_KEYS = ('displacement_m', 'stroke_displacement_m')
# The contract speaks prose; the audit writes codes. Keys must stay in sync with
# classify_attempt(), and an unknown code fails loudly instead of guessing.
CONTRACT_CODES = {
    None: 'OK',
    'carry engaged': 'CARRIED',
    'object moved backwards': 'MOVED_BACKWARDS',
    'displacement missing': 'MISSING_REPORTED',
    'displacement not finite': 'NON_FINITE_REPORT',
    'unreadable result': 'UNREADABLE_RESULT',
}
CSV_COLUMNS = ('index', 'reported_progress_m', 'reported_counted_m', 'signed_source',
               'signed_net_m', 'difference_m', 'sign', 'code', 'net_code',
               'contact_made', 'carry_engaged_during', 'clears_floor')


class AuditError(Exception):
    """Input that cannot be audited; always surfaces as a non-zero exit."""


def fail(message):
    raise AuditError(message)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def cell(value):
    """CSV representation: floats round-trip, booleans are lowercase, None is empty."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else ''
    return value


def resolve(run, name, candidates=()):
    """Find one input file; an explicit name must resolve, a candidate list is optional."""
    if name is not None:
        path = Path(name)
        if not path.is_absolute():
            path = run / path
        if not path.is_file():
            fail('input file does not exist: %s' % path)
        return path
    for relative in candidates:
        path = run / relative
        if path.is_file():
            return path
    fail('no attempts file under %s; looked for %s. Pass --attempts.'
         % (run, ', '.join(candidates)))


def read_jsonl(path):
    """Return [(line_number, value)]. Malformed JSON is an error, not a skip.

    A line that parses but is not an object is kept: classify_attempt() already
    labels that "unreadable result", which is the policy's own answer.
    """
    rows = []
    for number, text in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), start=1):
        if not text.strip():
            continue
        try:
            rows.append((number, json.loads(text)))
        except ValueError as exc:
            fail('%s line %d is not JSON: %s' % (path, number, exc))
    if not rows:
        fail('%s has no rows; an audit of nothing is not an audit' % path)
    return rows


def pose_xy(value):
    """Extract planar (x, y) from a Pose-like value.

    Real ContactPush results carry ROS poses ({"position": {"x": ...}}); flat
    lists appear in older archives. Anything else is refused rather than guessed.
    """
    if isinstance(value, dict):
        if 'position' in value:
            return pose_xy(value['position'])
        if 'x' in value or 'y' in value:
            return pose_xy([value.get('x'), value.get('y')])
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [value[0], value[1]]
    return None


def endpoint_pose(row, keys):
    """First pose-like field among keys -> (x, y, reason)."""
    for key in keys:
        if key in row:
            pair = pose_xy(row[key])
            if pair is None:
                return None, 'MISSING_ENDPOINT'
            if not all(finite(v) for v in pair):
                return None, 'NON_FINITE'
            return [float(pair[0]), float(pair[1])], None
    return None, 'MISSING_ENDPOINT'


def reported_value(row):
    """Signed per-attempt displacement -> (value, signed_source, reason).

    displacement_along_direction_m is a projection and carries its sign.
    displacement_m is a magnitude: usable only as a marked fallback, because it
    cannot report that the object went backwards.
    """
    if isinstance(row, dict):
        for key in ALONG_KEYS:
            if key in row:
                if not finite(row[key]):
                    return None, 'along', 'NON_FINITE'
                return float(row[key]), 'along', None
        for key in MAGNITUDE_KEYS:
            if key in row:
                if not finite(row[key]):
                    return None, 'fallback', 'NON_FINITE'
                return float(row[key]), 'fallback', None
    return None, None, 'MISSING'


def normalise_direction(dx, dy):
    norm = math.hypot(dx, dy)
    if not finite(norm) or norm == 0:
        fail('--direction must be a non-zero finite vector, got %r,%r' % (dx, dy))
    return (dx / norm, dy / norm)


def parse_direction(text):
    parts = text.split(',')
    if len(parts) != 2:
        raise ValueError('expected "dx,dy"')
    dx, dy = (float(part) for part in parts)
    if not (finite(dx) and finite(dy)) or math.hypot(dx, dy) == 0:
        raise ValueError('components must be finite and not both zero')
    return normalise_direction(dx, dy)


def project(start, end, unit):
    dx, dy = end[0] - start[0], end[1] - start[1]
    return dx * unit[0] + dy * unit[1], math.hypot(dx, dy)


def classify_sign(projection, magnitude):
    """Sign is stated only where the projection clears the policy's own floor."""
    if magnitude < MIN_DISPLACEMENT_M:
        return 'UNKNOWN', 'NO_MOTION'
    if projection >= MIN_DISPLACEMENT_M:
        return 'POSITIVE', 'OK'
    if projection <= -MIN_DISPLACEMENT_M:
        return 'NEGATIVE', 'OK'
    return 'UNKNOWN', 'ZERO_PROJECTION'


def strict_endpoints(rows):
    """First row's before-pose and last row's after-pose: the run's own window."""
    start, start_reason = endpoint_pose(rows[0][1], BEFORE_KEYS)
    end, end_reason = endpoint_pose(rows[-1][1], AFTER_KEYS)
    return dict(start_row=rows[0][0], end_row=rows[-1][0], start_pose=start,
                end_pose=end, reason=start_reason or end_reason)


def partial_window(rows):
    """A sub-window measured over rows that do have endpoint poses.

    Reported separately from the run's net, and never substituted for it: a
    window that starts after attempt 1 is a different measurement.
    """
    first = last = None
    for number, row in rows:
        pose, reason = endpoint_pose(row, BEFORE_KEYS)
        if reason is None:
            first = (number, pose)
            break
    for number, row in reversed(rows):
        pose, reason = endpoint_pose(row, AFTER_KEYS)
        if reason is None:
            last = (number, pose)
            break
    if first is None or last is None or first[0] > last[0]:
        return None
    return {'start_row': first[0], 'end_row': last[0],
            'start_pose': first[1], 'end_pose': last[1],
            'note': 'sub-window, not the run net: rows outside the endpoint window were skipped'}


def require_recognised_rows(rows):
    """A file where not one row carries a known field is the wrong file.

    Reporting a whole run as UNKNOWN is correct for bad evidence and wrong for a
    contract mismatch, so the two are separated here instead of downstream.
    """
    fields = set(ALONG_KEYS + MAGNITUDE_KEYS + BEFORE_KEYS + AFTER_KEYS)
    if not any(isinstance(row, dict) and fields & set(row) for _, row in rows):
        fail('no attempt row carries a recognised displacement or pose field (%s); '
             'this does not look like a PushObject results file' % ', '.join(sorted(fields)))


def object_identity(rows):
    names = sorted({row.get('object_name') for _, row in rows
                    if isinstance(row, dict) and row.get('object_name') is not None})
    if len(names) > 1:
        fail('attempts span several objects (%s); audit each object separately'
             % ', '.join(str(name) for name in names))
    return names[0] if names else None


def audit_attempts(rows, direction, direction_source):
    unit = direction
    attempts = []
    for index, (number, row) in enumerate(rows, start=1):
        value, signed_source, report_reason = reported_value(row)
        made, counted, carry, code = classify_attempt(row)
        if code not in CONTRACT_CODES:
            fail('push_recover.classify_attempt returned an unmapped code %r; '
                 'update CONTRACT_CODES together with the contract' % (code,))
        before, before_reason = endpoint_pose(row, BEFORE_KEYS)
        after, after_reason = endpoint_pose(row, AFTER_KEYS)
        signed_net = sign = net_code = None
        if unit is None:
            net_code = 'NO_DIRECTION'
        elif before_reason is not None or after_reason is not None:
            net_code = before_reason or after_reason
        elif before is None or after is None:
            net_code = 'MISSING_ENDPOINT'
        else:
            projection, magnitude = project(before, after, unit)
            signed_net = projection
            sign, net_code = classify_sign(projection, magnitude)
        difference = None
        if value is not None and signed_net is not None:
            difference = value - signed_net
        if net_code in ('MISSING_ENDPOINT', 'NON_FINITE', 'NO_DIRECTION'):
            sign = 'UNKNOWN'
        attempts.append(dict(
            index=index, line=number, reported_progress_m=value,
            reported_counted_m=float(counted), signed_source=signed_source,
            report_code=CONTRACT_CODES[code],
            contract_reason=report_reason, signed_net_m=signed_net,
            difference_m=difference, sign=sign or 'UNKNOWN', net_code=net_code,
            contact_made=bool(made), carry_engaged_during=bool(carry),
            clears_floor=bool(is_progress(value)) if value is not None else False))
    return attempts


def summarise(attempts, endpoints, direction, direction_source, partial):
    values = [a['reported_progress_m'] for a in attempts]
    # A total over a set that is missing an attempt is not the run's total; the
    # flag travels with the number so a reader cannot be quietly misled by it.
    reported_complete = all(value is not None for value in values)
    reported_total = sum(value for value in values if value is not None)
    counted_total = sum(a['reported_counted_m'] for a in attempts)
    non_finite = any(a['net_code'] == 'NON_FINITE' or a['report_code'] == 'NON_FINITE_REPORT'
                     for a in attempts)
    # The net is measured whenever the endpoints support it, even if another part
    # of the evidence is unusable: "the net is measured but the report is not" is
    # a more useful answer than discarding both.
    net_total = None
    sign, measured_code = 'UNKNOWN', None
    if direction is None:
        measured_code = 'NO_DIRECTION'
    elif endpoints['reason'] is not None:
        measured_code = endpoints['reason']
    else:
        projection, magnitude = project(endpoints['start_pose'], endpoints['end_pose'], direction)
        net_total = projection
        sign, measured_code = classify_sign(projection, magnitude)
    # Primary code, most fundamental blocker first; every code is still counted in
    # reasons, so nothing is hidden by this ordering.
    for candidate in ('NO_DIRECTION', 'NON_FINITE'):
        if measured_code == candidate or (candidate == 'NON_FINITE' and non_finite):
            code = candidate
            break
    else:
        code = measured_code
    reasons = {}
    for attempt in attempts:
        for key in (attempt['report_code'], attempt['net_code']):
            if key and key != 'OK':
                reasons[key] = reasons.get(key, 0) + 1
    if code and code != 'OK':
        reasons[code] = reasons.get(code, 0) + 1
    off_by_floor = sum(1 for a in attempts
                       if a['difference_m'] is not None
                       and abs(a['difference_m']) >= MIN_DISPLACEMENT_M)
    caveats = []
    fallback = sum(1 for a in attempts if a['signed_source'] == 'fallback')
    if fallback:
        caveats.append('%d attempt(s) reported only displacement_m, an unsigned magnitude: '
                       'those values carry no sign evidence' % fallback)
    if direction_source == 'derived':
        caveats.append('direction was derived from the same endpoint displacement it is '
                       'projected onto; a sign measured that way cannot contradict itself')
    if endpoints['reason'] is not None and partial is not None:
        caveats.append('endpoint poses missing; partial_window is a sub-window measurement '
                       'and is not the run net')
    return dict(
        # MEASURED means the audit completed with a usable sign; UNKNOWN means at
        # least one piece of evidence could not support the comparison.
        status='MEASURED' if code == 'OK' else 'UNKNOWN', sign=sign, code=code,
        reported_total_m=reported_total, reported_total_complete=reported_complete,
        reported_counted_total_m=counted_total,
        signed_net_total_m=net_total, net_complete=net_total is not None,
        difference_total_m=((reported_total - net_total)
                            if net_total is not None and reported_complete else None),
        counted_minus_net_m=(counted_total - net_total) if net_total is not None else None,
        attempts=len(attempts),
        attempts_clearing_floor=sum(1 for a in attempts if a['clears_floor']),
        contact_made_attempts=sum(1 for a in attempts if a['contact_made']),
        carry_engaged_attempts=sum(1 for a in attempts if a['carry_engaged_during']),
        signed_source_counts={key: sum(1 for a in attempts if a['signed_source'] == key)
                             for key in ('along', 'fallback') if any(
                                 a['signed_source'] == key for a in attempts)},
        rows_reported_off_by_more_than_floor=off_by_floor,
        reasons=reasons, caveats=caveats)


# CSV column -> attempt key. "code" is the contract's report classification;
# "net_code" is the independent measurement's own status.
CSV_FIELDS = dict((column, column) for column in CSV_COLUMNS)
CSV_FIELDS['code'] = 'report_code'


def write_csv(path, attempts):
    with Path(path).open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(CSV_COLUMNS)
        for attempt in attempts:
            writer.writerow([cell(attempt[CSV_FIELDS[column]]) for column in CSV_COLUMNS])


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
        out = run.parent / ('%s-audit-%s%s' % (stem, stamp, suffix))
        try:
            out.mkdir()
            return out
        except FileExistsError:
            continue
    fail('cannot create a fresh output directory next to %s' % run)


def audit(run, attempts_path, out_dir, direction):
    run = Path(run).resolve()
    if not run.is_dir():
        fail('run directory does not exist: %s' % run)
    attempts_path = resolve(run, attempts_path, ATTEMPT_CANDIDATES)
    before = {str(attempts_path): sha256_file(attempts_path),
              'bytes': attempts_path.stat().st_size}
    rows = read_jsonl(attempts_path)
    require_recognised_rows(rows)
    object_name = object_identity(rows)
    endpoints = strict_endpoints(rows)

    if direction is None:
        if endpoints['reason'] is None and endpoints['start_pose'] is not None:
            dx = endpoints['end_pose'][0] - endpoints['start_pose'][0]
            dy = endpoints['end_pose'][1] - endpoints['start_pose'][1]
            direction = normalise_direction(dx, dy) if math.hypot(dx, dy) >= MIN_DISPLACEMENT_M else None
        direction_source = 'derived' if direction is not None else 'unavailable'
    else:
        direction_source = 'explicit'

    partial = partial_window(rows) if endpoints['reason'] is not None else None
    attempts = audit_attempts(rows, direction, direction_source)
    summary = summarise(attempts, endpoints, direction, direction_source, partial)
    summary.update(
        kind=KIND, run_dir=str(run), out_dir=str(out_dir),
        attempts_path=str(attempts_path), object_name=object_name,
        direction=(None if direction is None else
                   dict(dx=direction[0], dy=direction[1], unit=list(direction),
                        source=direction_source)),
        min_displacement_m=MIN_DISPLACEMENT_M, endpoints=endpoints,
        partial_window=partial,
        inputs=[dict(path=str(attempts_path), sha256=before[str(attempts_path)],
                     bytes=before['bytes'], rows=len(rows))],
        generated_utc_ns=time.time_ns(),
        # Deliberate negatives: this is a measurement audit, not an acceptance run.
        interpolation_used=False, policy_modified=False, task_success_claim=False,
        independent_acceptance_claim=False,
        definitions=dict(
            reported_progress_m='signed displacement the skill reported for that attempt',
            reported_counted_m='what push_recover.accumulate would count (negatives and carry zeroed)',
            signed_net_m='endpoint pose pair of that attempt projected onto the direction',
            difference_m='reported_progress_m - signed_net_m',
            difference_total_m='sum of reported - net over the whole run',
            counted_minus_net_m='sum of counted - net; the policy accumulation error'))
    write_csv(out_dir / 'attempts.csv', attempts)
    after = sha256_file(attempts_path)
    summary['inputs_unchanged'] = after == before[str(attempts_path)]
    with (out_dir / 'summary.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
        stream.write('\n')
    if not summary['inputs_unchanged']:
        fail('input changed while auditing: %s' % attempts_path)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='run directory containing the attempts JSONL')
    parser.add_argument('--out', type=Path,
                        help='new output directory (must not exist); defaults to RUN-audit-<utc>')
    parser.add_argument('--attempts',
                        help='attempts JSONL, absolute or relative to the run directory')
    parser.add_argument('--direction', help='task direction as dx,dy (planar); derived when omitted')
    args = parser.parse_args(argv)
    direction = None
    if args.direction is not None:
        try:
            direction = parse_direction(args.direction)
        except ValueError as exc:
            parser.error('--direction: %s' % exc)
    try:
        out_dir = choose_out(args.run.resolve(), args.out)
        summary = audit(args.run, args.attempts, out_dir, direction)
    except AuditError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 2
    print(json.dumps(dict(kind=summary['kind'], status=summary['status'],
                          sign=summary['sign'], code=summary['code'],
                          attempts=summary['attempts'],
                          signed_net_total_m=summary['signed_net_total_m'],
                          out=str(out_dir)), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
