#!/usr/bin/env python3
"""Accept a finished run from artifacts, never from the agent's self-report.

WHY THIS FILE EXISTS
result.json is written by the same task process whose work is being graded, so
`status: PASS` in it proves that the process was willing to say PASS - not that
the box moved. The numbers that are not authored by the planner are the
per-skill JSONL logs: verify.jsonl and place.jsonl are emitted after the fact
from the Gazebo pose stream by the skill servers. This script accepts a run only
when the typed task result agrees with those independent measurements.

Every failing reason is collected instead of stopping at the first one: a run
that fails for three reasons must not look like a run that fails for one, or a
repair will chase the wrong defect.

WHAT IT READS
  result.json         -> status, task.outcome, task.error_code,
                         task.final_position_error_m
  skills/verify.jsonl -> last line's detail, "... (err=0.0130)" in metres
  skills/place.jsonl  -> last line's detail, "drop error 0.013m" in metres

RUN_DIR may be one run directory or a window label directory holding exactly one
run-* child. A window with two or more run-* children is ambiguous and fails,
because accepting one of them would let a rerun silently grade whichever
directory happened to sort first. A window with none is left to the artifact
checks, where the missing result.json fails loudly.

WHY A MISSING VERIFY IS A FAILURE, NOT A WARNING
An absent measurement is not evidence of success; observe_from_run.py reports
unmeasured objects as ABSENT for the same reason. Dual-object tasks do not emit
task.final_position_error_m, so that field is a warning only - verify.jsonl owns
the physical threshold, and the field is reported for the record.

Exit codes: 0 accepted, 1 rejected, 2 usage or I/O error.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

# Skill detail strings are human-readable, so the number may carry a unit.
_NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
_UNIT = r'(mm|cm|m)?'
_VERIFY_ERR = re.compile(r'err\s*=\s*(' + _NUMBER + r')\s*' + _UNIT, re.IGNORECASE)
_PLACE_DROP = re.compile(r'drop\s+error\s*[:=]?\s*(' + _NUMBER + r')\s*' + _UNIT,
                         re.IGNORECASE)

_UNIT_TO_MM = {'m': 1000.0, 'cm': 10.0, 'mm': 1.0}

_METRIC_KEYS = ('final_error_mm', 'place_drop_mm', 'verify_error_mm',
                'place_verify_delta_mm')


def _is_number(value):
    """True for a real finite number. bool is excluded on purpose (it is an int)."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _measure_to_mm(detail, pattern):
    """Pull the first measurement out of a skill detail string, in millimetres.

    Detail text is written for humans ("drop error 0.013m"), so the unit may be
    omitted. An unqualified number is metres because every skill server in this
    repository logs its distances in metres; guessing millimetres here would
    turn an 8 mm placement error into a pass.
    """
    if not isinstance(detail, str):
        return None
    match = pattern.search(detail)
    if match is None:
        return None
    try:
        value = float(match.group(1))
    except (TypeError, ValueError):
        return None
    factor = _UNIT_TO_MM[(match.group(2) or 'm').lower()]
    value *= factor
    return value if math.isfinite(value) else None


def _last_detail(path):
    """Return the detail of the newest JSONL row, or None.

    Only the last non-empty line is considered. It is the newest measurement,
    and falling back to an older row would silently accept a run whose latest
    write was truncated - exactly the kind of half-written evidence this gate
    exists to reject.
    """
    try:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(row, dict):
            return None
        return row.get('detail')
    return None


def _resolve_run_dir(root):
    """Resolve a run directory or a single-run window label directory.

    Returns (run_dir, reasons). Ambiguity is a rejection rather than a choice:
    picking one of several runs would make the verdict depend on sort order.
    """
    run_dir = root
    if not (root / 'result.json').exists():
        windows = sorted(p for p in root.iterdir()
                         if p.is_dir() and p.name.startswith('run-'))
        if len(windows) == 1:
            run_dir = windows[0]
        elif len(windows) > 1:
            return root, [
                'multiple run-* directories under %s (found %d); expected exactly one'
                % (root, len(windows))]
    return run_dir, []


def _report(run_dir, reasons, warnings, metrics):
    return {
        'pass': not reasons,
        'reasons': list(reasons),
        'warnings': list(warnings),
        'metrics': dict(metrics),
        'run_dir': str(Path(run_dir).resolve()),
    }


def evaluate(run_dir, max_delta_mm=1.0):
    """Grade one run directory and return the report dict.

    Every check runs even after an earlier one fails, so the report names all
    defects. OSError is raised only when RUN_DIR itself is missing: artifacts
    that are missing inside an existing run are findings, not usage errors.
    """
    root = Path(run_dir)
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    resolved, reasons = _resolve_run_dir(root)
    metrics = dict.fromkeys(_METRIC_KEYS)
    warnings = []
    if reasons:
        return _report(resolved, reasons, warnings, metrics)

    # 1. result.json exists and parses. Without a typed result there is nothing
    #    to accept; a corrupt file must never be read as an implicit pass.
    result = None
    result_path = resolved / 'result.json'
    if not result_path.exists():
        reasons.append('missing result.json')
    else:
        try:
            result = json.loads(result_path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            reasons.append('result.json does not parse: %s' % exc)
        else:
            if not isinstance(result, dict):
                reasons.append('result.json is not a JSON object')
                result = None

    task = result.get('task') if isinstance(result, dict) else None

    # 2. status is the runner's aggregate verdict. It can disagree with the
    #    task block (e.g. a launch failure after a successful task), so it is
    #    checked rather than inferred from task.outcome.
    if isinstance(result, dict) and result.get('status') != 'PASS':
        reasons.append('status is %r, expected PASS' % (result.get('status'),))

    # 3/4. The typed task contract is what downstream code branches on. A
    #    success with a non-zero error code is a contradiction, not a pass.
    if isinstance(task, dict):
        if task.get('outcome') != 'OUTCOME_SUCCEEDED':
            reasons.append('task.outcome is %r, expected OUTCOME_SUCCEEDED'
                           % (task.get('outcome'),))
        if task.get('error_code') != 'ERR_NONE':
            reasons.append('task.error_code is %r, expected ERR_NONE'
                           % (task.get('error_code'),))
    elif isinstance(result, dict):
        reasons.append('result.json has no task object')

    # 7. final_position_error_m is informational. Dual-object tasks do not
    #    report it, so absence is a warning, never a failure.
    if isinstance(task, dict):
        if task.get('final_position_error_m') is None:
            warnings.append('task.final_position_error_m absent; '
                            'dual-object tasks do not report it')
        elif _is_number(task.get('final_position_error_m')):
            metrics['final_error_mm'] = round(
                task['final_position_error_m'] * 1000.0, 6)
        else:
            warnings.append('task.final_position_error_m is not numeric (%r); '
                            'not reported' % (task.get('final_position_error_m'),))

    # 5. verify.jsonl is the independent measurement. Missing or unparseable is
    #    a rejection, because "not measured" is not "measured good".
    verify_mm = _measure_to_mm(
        _last_detail(resolved / 'skills' / 'verify.jsonl'), _VERIFY_ERR)
    if verify_mm is None:
        reasons.append('no independent verify measurement')
    else:
        metrics['verify_error_mm'] = round(verify_mm, 6)

    # 6. place.jsonl is a second measurement of the same release, taken at a
    #    different moment. A gap beyond the tolerance means one of them is
    #    stale or wrong; accepting either would launder a real error. Absence
    #    of place evidence is allowed (verify already owns the verdict).
    place_mm = _measure_to_mm(
        _last_detail(resolved / 'skills' / 'place.jsonl'), _PLACE_DROP)
    if place_mm is not None:
        metrics['place_drop_mm'] = round(place_mm, 6)
    if place_mm is not None and verify_mm is not None:
        delta = abs(place_mm - verify_mm)
        metrics['place_verify_delta_mm'] = round(delta, 6)
        # 1e-9 covers float noise from the metre->millimetre conversion only.
        if delta > max_delta_mm + 1e-9:
            reasons.append('place/verify disagree')

    return _report(resolved, reasons, warnings, metrics)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Accept a finished run from its artifacts, not its self-report.')
    parser.add_argument('run_dir', type=Path,
                        help='run directory, or window label directory with '
                             'exactly one run-* child')
    parser.add_argument('--json', dest='json_out', type=Path,
                        help='also write the report to this path')
    parser.add_argument('--max-delta-mm', type=float, default=1.0,
                        help='largest tolerated place/verify disagreement in mm '
                             '(default 1.0)')
    args = parser.parse_args(argv)
    if not math.isfinite(args.max_delta_mm) or args.max_delta_mm < 0:
        parser.error('--max-delta-mm must be a non-negative finite number')

    try:
        report = evaluate(args.run_dir, max_delta_mm=args.max_delta_mm)
    except OSError as exc:
        print('accept_run: %s' % exc, file=sys.stderr)
        return 2

    encoded = json.dumps(report, indent=2)
    if args.json_out is not None:
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(encoded + '\n', encoding='utf-8')
        except OSError as exc:
            print('accept_run: cannot write %s: %s' % (args.json_out, exc),
                  file=sys.stderr)
            return 2

    line = 'ACCEPT %s %s' % ('PASS' if report['pass'] else 'FAIL',
                             report['run_dir'])
    if report['reasons']:
        line += ' ' + ' | '.join(report['reasons'])
    print(line)
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
