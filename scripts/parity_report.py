"""Compare the same declared tasks across carry backends, with their own tolerances.

Legacy parity is not "the joint backend also worked once": it is the same manifest,
the same declared tolerance and the same success criterion on every backend. This
report refuses to compare windows that were declared differently, never turns a
missing case into a pass, and reports the per-case attempt counts and the verifier's
own measured error, so an accuracy gap cannot hide behind a case-level PASS.
"""
import json
from pathlib import Path

from contact_gate import require


def rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load(path):
    window = json.loads(Path(path).read_text())
    require(window.get('declaration_sha256'), 'window has no declaration identity')
    return window


def resolve_run(entry, base):
    """A window records where its run lived; a receipt beside it may hold the rows."""
    if not entry:
        return None
    run = Path(entry)
    if run.exists():
        return run
    candidate = Path(base) / run.name
    return candidate if candidate.exists() else None


def run_metrics(run):
    """Attempt counts and the worst error the verifier measured in this run.

    A case can place more than one object (the dual-object demo does), so taking the
    first or the last verification would let a bad placement hide behind a good one.
    The worst verified error is reported, with how many verifications produced it.
    """
    picks, places = rows(run / 'skills/pick.jsonl'), rows(run / 'skills/place.jsonl')
    verifies = rows(run / 'skills/verify.jsonl')
    errors = [row['position_error_m'] for row in verifies
              if isinstance(row.get('position_error_m'), (int, float))]
    tolerances = [row['tolerance_m'] for row in verifies
                  if isinstance(row.get('tolerance_m'), (int, float))]
    return dict(pick_attempts=len(picks), place_attempts=len(places),
                verify_count=len(verifies),
                verify_error_m=max(errors) if errors else None,
                verify_tolerance_m=min(tolerances) if tolerances else None)


def case_rows(window, base=None):
    result = []
    for episode in window['episodes']:
        outcome = episode['result']
        task = outcome.get('task') or {}
        row = dict(case=episode['case'], object=episode['object'],
                   status=outcome.get('status'),
                   outcome=task.get('outcome'), error_code=task.get('error_code'),
                   task_error_m=task.get('final_position_error_m'),
                   expectation_met=outcome.get('expectation_met'))
        run = resolve_run(episode.get('run'), base)
        row['receipt'] = bool(run)
        if run is not None:
            row.update(run_metrics(run))
        result.append(row)
    return result


def compare(paths, *, expected_cases=5):
    require(len(paths) >= 2, 'parity needs at least two backends')
    windows = [(Path(path).parent.name, load(path), Path(path).parent) for path in paths]
    digests = {window['declaration_sha256'] for _, window, _ in windows}
    require(len(digests) == 1, 'the windows were not declared from the same manifest')
    for name, window, _ in windows:
        require(len(window['episodes']) == expected_cases,
                '%s did not run the declared number of cases' % name)
    cases = [{'case': episode['case'], 'object': episode['object']}
             for episode in windows[0][1]['episodes']]
    for name, window, _ in windows:
        got = [{'case': episode['case'], 'object': episode['object']} for episode in window['episodes']]
        require(got == cases, '%s ran a different case list' % name)
    table, offenders, tolerances = {}, [], set()
    for name, window, base in windows:
        measured_rows = case_rows(window, base)
        table[name] = dict(status=window['status'], backend=window.get('backend'),
                           cases=measured_rows)
        for row in measured_rows:
            passed = row['status'] in ('PASS', 'EXPECTED_FAILURE') and row['expectation_met'] is True
            if not passed:
                offenders.append('%s/%s: %s' % (name, row['case'], row['status']))
            tolerance, error = row.get('verify_tolerance_m'), row.get('verify_error_m')
            if tolerance is None:
                continue
            tolerances.add(tolerance)
            if error is None:
                offenders.append('%s/%s: the verifier recorded no measured error'
                                 % (name, row['case']))
            elif not 0 <= error <= tolerance:
                offenders.append('%s/%s: verified error %.4f m exceeds the declared %.4f m'
                                 % (name, row['case'], error, tolerance))
    require(not offenders, 'parity broken: ' + '; '.join(offenders))
    require(len(tolerances) <= 1, 'the backends were verified against different tolerances')
    observed = {}
    for name, value in table.items():
        errors = [row['verify_error_m'] for row in value['cases']
                  if row.get('verify_error_m') is not None]
        observed[name] = max(errors) if errors else None
    return dict(status='CARRY_BACKEND_PARITY_PASS', declaration_sha256=digests.pop(),
                backends={name: value['backend'] for name, value in table.items()},
                cases=cases, table=table,
                declared_tolerance_m=(tolerances.pop() if tolerances else None),
                max_verified_error_m=observed,
                attempts={name: {row['case']: row.get('pick_attempts') for row in value['cases']}
                          for name, value in table.items()},
                tolerance_moved=False,
                interpretation='Same manifest, same declared tolerance and the same criterion on '
                               'every backend; the per-backend error spread is reported, not '
                               'flattened into the verdict. One bounded window per backend, '
                               'not a success rate')


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('windows', nargs='+', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = compare(args.windows)
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.out:
        args.out.write_text(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
