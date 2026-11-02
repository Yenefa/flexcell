"""Compare the same declared tasks across carry backends without moving a threshold.

Legacy parity is not "the joint backend also worked once": it is the same manifest,
the same tolerances and the same success criterion applied to every backend. This
report refuses to compare windows that were declared differently, and never turns a
missing case into a pass.
"""
import json
from pathlib import Path

from contact_gate import require


def load(path):
    window = json.loads(Path(path).read_text())
    require(window.get('declaration_sha256'), 'window has no declaration identity')
    return window


def case_rows(window):
    rows = []
    for episode in window['episodes']:
        result = episode['result']
        task = result.get('task') or {}
        rows.append(dict(case=episode['case'], object=episode['object'],
                         status=result.get('status'),
                         outcome=task.get('outcome'), error_code=task.get('error_code'),
                         placement_error_m=task.get('final_position_error_m'),
                         expectation_met=result.get('expectation_met')))
    return rows


def compare(paths, *, max_placement_error_m=.012, expected_cases=5):
    require(len(paths) >= 2, 'parity needs at least two backends')
    windows = [(Path(path).parent.name, load(path)) for path in paths]
    digests = {window['declaration_sha256'] for _, window in windows}
    require(len(digests) == 1, 'the windows were not declared from the same manifest')
    for name, window in windows:
        require(len(window['episodes']) == expected_cases,
                '%s did not run the declared number of cases' % name)
    cases = [{'case': episode['case'], 'object': episode['object']}
             for episode in windows[0][1]['episodes']]
    for name, window in windows:
        got = [{'case': episode['case'], 'object': episode['object']} for episode in window['episodes']]
        require(got == cases, '%s ran a different case list' % name)
    table, offenders = {}, []
    for name, window in windows:
        rows = case_rows(window)
        table[name] = dict(status=window['status'], backend=window.get('backend'), cases=rows)
        for row in rows:
            passed = row['status'] in ('PASS', 'EXPECTED_FAILURE') and row['expectation_met'] is True
            if not passed:
                offenders.append('%s/%s: %s' % (name, row['case'], row['status']))
            if row['placement_error_m'] is not None and row['placement_error_m'] > max_placement_error_m:
                offenders.append('%s/%s: placement error %.4f m exceeds %.4f m'
                                 % (name, row['case'], row['placement_error_m'], max_placement_error_m))
    require(not offenders, 'parity broken: ' + '; '.join(offenders))
    return dict(status='CARRY_BACKEND_PARITY_PASS', declaration_sha256=digests.pop(),
                backends={name: value['backend'] for name, value in table.items()},
                cases=cases, table=table,
                max_placement_error_m=max_placement_error_m,
                tolerance_moved=False,
                interpretation='Same manifest, same tolerance and the same criterion on every '
                               'backend; one bounded window per backend, not a success rate')


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
