#!/usr/bin/env python3
"""Report push progress and net displacement from archived run reports (read-only).

Two different quantities get called "how far the box moved". This tool keeps them
apart and prints the difference instead of collapsing them into one number.

* progress_m - the sum of the displacement_along_direction_m each action report
  carries. It is what the executor claims each bounded push achieved, measured
  along that action's own requested direction. Only defined when every report in
  the run carries a finite value.
* net_m - the signed projection of (last measured_after - first measured_before)
  on the task direction. It is what the object actually did between the first and
  the last measurement, regardless of how many actions ran in between.
* difference_m - net_m - progress_m. A non-zero difference means the per-action
  reports do not partition the object's motion: overlapping measurement windows,
  motion that no report covers, a retract that drags the object, or an action
  whose report is missing.

This is a diagnostic tool. It never decides whether the task passed, never
changes a run, and never writes inside the run it reads.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

UNKNOWN = 'UNKNOWN'
KNOWN = 'KNOWN'
NOT_A_VERDICT = 'NOT_EVALUATED_BY_THIS_TOOL'

POINT = re.compile(r'Point\(x=([^,]+),\s*y=([^,]+),\s*z=([^)]+)\)')


def _number(value):
    """Return a finite float, or None. JSON NaN/Infinity are not measurements."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_position(text):
    """Pull the position out of a recorded ROS pose repr. None when unusable."""
    if not isinstance(text, str):
        return None
    match = POINT.search(text)
    if not match:
        return None
    triple = tuple(_number(part) for part in match.groups())
    return None if any(part is None for part in triple) else triple


def plane_direction(vector):
    """Normalise an arbitrary planar direction. Raises ValueError on a zero vector."""
    values = [_number(component) for component in (vector or [])]
    if len(values) != 2 or any(value is None for value in values):
        raise ValueError('direction must be two finite numbers: ' + repr(vector))
    norm = math.hypot(*values)
    if not norm:
        raise ValueError('direction must not be the zero vector')
    return (values[0] / norm, values[1] / norm)


def project_along(delta, direction):
    """Signed scalar of a 3-D delta along a normalised planar direction."""
    return delta[0] * direction[0] + delta[1] * direction[1]


def project_lateral(delta, direction):
    """Unsigned component perpendicular to the direction, in the plane."""
    return abs(-delta[0] * direction[1] + delta[1] * direction[0])


def _subtract(after, before):
    return tuple(a - b for a, b in zip(after, before))


def task_direction(task, object_name=None):
    """Return (object name, normalised direction) declared by the task file."""
    goals = ((task or {}).get('expected_goal') or {}).get('push') or {}
    if not goals:
        raise ValueError('task has no expected_goal.push entry')
    if object_name is None:
        if len(goals) != 1:
            raise ValueError('task pushes several objects; pass --object')
        object_name = next(iter(goals))
    if object_name not in goals:
        raise ValueError('task has no push goal for ' + object_name)
    direction = goals[object_name].get('direction')
    if direction is None:
        raise ValueError('task push goal has no direction for ' + object_name)
    return object_name, plane_direction(direction)


def load_reports(paths):
    """Load push reports in the given order. Raises ValueError on unusable input."""
    reports = []
    for path in paths:
        try:
            payload = json.loads(Path(path).read_text())
        except (OSError, ValueError) as exc:
            raise ValueError('unreadable report ' + str(path) + ': ' + str(exc))
        if not isinstance(payload, dict):
            raise ValueError('report is not an object: ' + str(path))
        reports.append((Path(path), payload))
    return reports


def _direction_sign(payload):
    """Sign of the recorded direction cosine: which way the object went relative to
    the direction that action requested. None when the report does not say."""
    value = _number(payload.get('direction_cos'))
    if value is None:
        return None
    return 1 if value > 0 else -1 if value < 0 else 0


def _requested_directions(payloads):
    """Are all attempts executed along the same requested direction?

    A recovery attempt re-plans its requested direction from the pose it finds.
    When the recorded direction cosines disagree in sign, the per-attempt
    displacement values are measured along different directions and their sum is
    not a displacement of anything. A single attempt is trivially consistent.
    """
    if len(payloads) < 2:
        return KNOWN, []
    signs = [_direction_sign(payload) for payload in payloads]
    reasons = []
    if any(sign is None for sign in signs):
        reasons.append('an attempt does not record direction_cos')
    if len({sign for sign in signs if sign is not None}) > 1:
        reasons.append('attempts were requested along different directions; their sum is not a displacement')
    return (UNKNOWN, reasons) if reasons else (KNOWN, [])


def _status_of(values):
    reasons = sorted({reason for value, reason in values if value is None})
    return dict(status=UNKNOWN if reasons else KNOWN, reasons=reasons)


def audit(reports, direction):
    """Build the diagnostic report. reports is [(path, payload), ...] in order."""
    if not reports:
        raise ValueError('no push reports')
    attempts = []
    progress_values = []
    for index, (path, payload) in enumerate(reports):
        before = parse_position(payload.get('measured_before'))
        after = parse_position(payload.get('measured_after'))
        reported = _number(payload.get('displacement_along_direction_m'))
        reason = None
        if reported is None:
            reason = 'report {0} has no finite displacement_along_direction_m'.format(path.name)
        recomputed = None
        if before is not None and after is not None:
            recomputed = project_along(_subtract(after, before), direction)
        progress_values.append((reported, reason))
        attempts.append(dict(
            index=index,
            report=path.name,
            status=payload.get('status'),
            outcome=payload.get('outcome'),
            error_code=payload.get('error_code'),
            requested_distance_m=_number(payload.get('requested_distance_m')),
            reported_progress_m=reported,
            recomputed_progress_m=recomputed,
            poses_complete=before is not None and after is not None,
            increments_executed=payload.get('increments_executed'),
            direction_cos=_number(payload.get('direction_cos')),
        ))

    consistency, consistency_reasons = _requested_directions([payload for _, payload in reports])
    progress = _status_of(progress_values)
    if consistency == UNKNOWN:
        progress = dict(status=UNKNOWN, reasons=progress['reasons'] + consistency_reasons)
    progress['requested_directions'] = consistency
    progress['value_m'] = (math.fsum(value for value, _ in progress_values)
                           if progress['status'] == KNOWN else None)

    first_before = parse_position(reports[0][1].get('measured_before'))
    last_after = parse_position(reports[-1][1].get('measured_after'))
    net = dict(status=UNKNOWN, reasons=[], value_m=None, magnitude_m=None,
               lateral_m=None, delta_z_m=None)
    missing = []
    if first_before is None:
        missing.append('the first report has no usable measured_before')
    if last_after is None:
        missing.append('the last report has no usable measured_after')
    if missing:
        net['reasons'] = missing
    else:
        delta = _subtract(last_after, first_before)
        net.update(status=KNOWN, value_m=project_along(delta, direction),
                   magnitude_m=math.hypot(delta[0], delta[1]),
                   lateral_m=project_lateral(delta, direction), delta_z_m=delta[2])

    difference = dict(status=UNKNOWN, reasons=[], value_m=None)
    if progress['status'] == KNOWN and net['status'] == KNOWN:
        difference.update(status=KNOWN, value_m=net['value_m'] - progress['value_m'])
    else:
        if progress['status'] == UNKNOWN:
            difference['reasons'].append('progress is unknown')
        if net['status'] == UNKNOWN:
            difference['reasons'].append('net displacement is unknown')

    return dict(
        task_outcome=NOT_A_VERDICT,
        direction=list(direction),
        attempt_count=len(reports),
        attempts=attempts,
        progress=progress,
        net=net,
        difference=difference,
        definitions=dict(
            progress_m='sum of the per-report displacement_along_direction_m',
            net_m='signed projection of (last measured_after - first measured_before) on the task direction',
            difference_m='net_m - progress_m; non-zero means the reports do not partition the motion',
        ),
    )


def render_markdown(result):
    """Human-readable view. Same facts as the JSON, no conclusion added."""
    lines = ['# Push progress vs net displacement', '',
             'Task outcome: **not evaluated by this tool** (diagnostic facts only).', '',
             'Direction (unit, planar): ({0:.6f}, {1:.6f})'.format(*result['direction']), '',
             '| # | report | requested m | reported progress m | recomputed m | poses |',
             '| - | - | - | - | - | - |']
    for attempt in result['attempts']:
        def cell(value):
            return 'n/a' if value is None else '{0:.6f}'.format(value)
        lines.append('| {index} | {report} | {requested} | {reported} | {recomputed} | {poses} |'.format(
            index=attempt['index'], report=attempt['report'],
            requested=cell(attempt['requested_distance_m']),
            reported=cell(attempt['reported_progress_m']),
            recomputed=cell(attempt['recomputed_progress_m']),
            poses='yes' if attempt['poses_complete'] else 'missing'))
    lines += ['', '## Quantities', '']
    for key, label in (('progress', 'Progress'), ('net', 'Net displacement'),
                       ('difference', 'Difference (net - progress)')):
        section = result[key]
        if section['status'] == KNOWN:
            lines.append('- **{0}**: {1:.6f} m'.format(label, section['value_m']))
        else:
            lines.append('- **{0}**: {1} - {2}'.format(label, UNKNOWN, '; '.join(section['reasons'])))
    lines += ['', 'Definitions:']
    for key, text in result['definitions'].items():
        lines.append('- {0}: {1}'.format(key, text))
    return '\n'.join(lines) + '\n'


def collect(paths, run_dir):
    """Expand a run directory into ordered report paths, keeping explicit paths as given."""
    collected = [Path(path) for path in paths]
    if run_dir is not None:
        collected.extend(sorted(Path(run_dir).rglob('push_*.json')))
    ordered = []
    seen = set()
    for path in collected:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(path)
    return ordered


def _digest(paths):
    return [dict(path=str(path), sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
            for path in paths]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--task', type=Path, required=True,
                        help='Frozen task file; supplies the push direction')
    parser.add_argument('--object', help='Object name when the task pushes several')
    parser.add_argument('--run-dir', type=Path, help='Directory holding push_*.json (searched recursively)')
    parser.add_argument('--report', type=Path, action='append', default=[],
                        help='Explicit push report, repeatable; overrides directory order')
    parser.add_argument('--out', type=Path, required=True,
                        help='New directory for the diagnostic output; never inside the input')
    args = parser.parse_args(argv)

    try:
        task = json.loads(args.task.read_text())
    except (OSError, ValueError) as exc:
        print('cannot read task file: ' + str(exc), file=sys.stderr)
        return 2
    try:
        object_name, direction = task_direction(task, args.object)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report_paths = collect(args.report, args.run_dir)
    if not report_paths:
        print('no push reports given; pass --run-dir or --report', file=sys.stderr)
        return 2

    out = args.out.resolve()
    for path in report_paths:
        resolved = path.resolve()
        if resolved == out or out in resolved.parents:
            print('refusing to write output inside an input: ' + str(path), file=sys.stderr)
            return 2
    if args.run_dir is not None:
        run_root = args.run_dir.resolve()
        if out == run_root or run_root in out.parents:
            print('refusing to write output inside the run directory', file=sys.stderr)
            return 2
    if out.exists() and any(out.iterdir()):
        print('output directory is not empty: ' + str(out), file=sys.stderr)
        return 2

    try:
        reports = load_reports(report_paths)
        result = audit(reports, direction)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result['inputs'] = dict(task=str(args.task), object=object_name,
                            reports=[str(path) for path in report_paths],
                            digests=_digest(report_paths))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'push_net_displacement.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'push_net_displacement.md').write_text(render_markdown(result))
    print(json.dumps(dict(progress=result['progress'], net=result['net'],
                          difference=result['difference'],
                          task_outcome=result['task_outcome']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())