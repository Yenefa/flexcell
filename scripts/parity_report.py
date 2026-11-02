"""Read-only carry comparison from complete windows and actual verify receipts."""
import json
import math
from pathlib import Path, PurePosixPath

from contact_gate import require

CASES = [('normal', 'target_box_a'), ('normal', 'target_box_b'),
         ('dual_object', 'target_box_a'), ('recovery_once', 'target_box_a'),
         ('budget_exhaustion', 'target_box_a')]
BACKENDS = {'teleport', 'velocity_servo', 'detachable_joint'}


def number(value, label, *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value) and
            (value > 0 if positive else value >= 0), label + ' must be finite, numeric and nonnegative')
    return value


def load(path):
    window = json.loads(Path(path).read_text())
    require(isinstance(window, dict) and window.get('declaration_sha256'), 'window has no declaration identity')
    require(window.get('status') == 'FUNCTIONAL_WINDOW_PASS', 'top-level window is not FUNCTIONAL_WINDOW_PASS')
    require(window.get('backend') in BACKENDS, 'missing or unknown carry backend')
    require(window.get('skill_backend') in {'legacy', 'mtc'}, 'missing or unknown skill backend')
    return window


def resolve_run(entry, base):
    """Original, transported trial/run and sealed flat layouts; never guess ties."""
    require(isinstance(entry, str) and bool(entry), 'missing run receipt path')
    portable = PurePosixPath(entry.replace('\\', '/'))
    require('..' not in portable.parts, 'run receipt path contains traversal')
    base = Path(base)
    choices = [Path(entry), base / portable.name]
    if not portable.is_absolute(): choices.append(base.joinpath(*portable.parts))
    if len(portable.parts) >= 2 and portable.parts[-2].startswith('trial-'):
        choices.append(base / portable.parts[-2] / portable.name)
    found = {p.resolve() for p in choices if p.is_dir()}
    require(len(found) == 1, 'missing or ambiguous run receipt: ' + entry)
    return found.pop()


def rows(path, *, required=False):
    if not path.is_file():
        require(not required, 'missing verify receipt: ' + str(path))
        return None
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    require(all(isinstance(row, dict) for row in result), 'invalid receipt row: ' + str(path))
    return result


def run_metrics(run, objects, *, negative):
    picks, places = rows(run / 'skills/pick.jsonl'), rows(run / 'skills/place.jsonl')
    verifies = rows(run / 'skills/verify.jsonl', required=not negative) or []
    result = dict(receipt=True, receipt_path=str(run),
                  pick_attempts=len(picks) if picks is not None else None,
                  place_attempts=len(places) if places is not None else None,
                  verify_count=len(verifies), verify_error_m=None,
                  verify_tolerance_m=None, object_errors_m={})
    if negative:
        require(not verifies, 'budget negative must not borrow placement verification')
        return result
    require(verifies, 'empty verify receipt')
    tolerances, latest = set(), {}
    for row in verifies:
        require(row.get('object_name') in objects, 'verify receipt belongs to another object')
        number(row.get('position_error_m'), 'verify placement error')
        tolerances.add(number(row.get('tolerance_m'), 'verify tolerance', positive=True))
        latest[row['object_name']] = row
    require(set(latest) == set(objects), 'missing object/zone verify receipt')
    require(len(tolerances) == 1, 'verify receipts have different tolerances')
    tolerance = tolerances.pop()
    for obj, row in latest.items():
        outcome = row.get('outcome')
        require((type(outcome) is int and outcome == 0 or outcome == '0') and
                row.get('verified') is True and type(row.get('error_code')) is int and row['error_code'] == 0,
                'terminal verify receipt did not succeed')
        require(row['position_error_m'] <= tolerance, 'placement error exceeds actual verifier tolerance')
        result['object_errors_m'][obj] = row['position_error_m']
    result.update(verify_error_m=max(result['object_errors_m'].values()), verify_tolerance_m=tolerance)
    return result


def case_rows(window, base):
    result = []
    for episode in window['episodes']:
        case, obj = episode['case'], episode['object']
        outcome = episode['result']; task = outcome.get('task') or {}
        negative = case == 'budget_exhaustion'
        require(outcome.get('expectation_met') is True, 'parity broken: case expectation not met')
        require(outcome.get('status') == ('EXPECTED_FAILURE' if negative else 'PASS'),
                'parity broken: unexpected case status')
        require(task.get('outcome') == ('OUTCOME_FAILED' if negative else 'OUTCOME_SUCCEEDED') and
                task.get('error_code') == ('ERR_RECOVERY_EXHAUSTED' if negative else 'ERR_NONE'),
                'parity broken: typed task outcome/error mismatch')
        if 'outcome_val' in task:
            require(type(task['outcome_val']) is int and task['outcome_val'] == (1 if negative else 0),
                    'parity broken: typed task value mismatch')
        run = resolve_run(episode.get('run'), base)
        objects = ['target_box_a', 'target_box_b'] if case == 'dual_object' else [obj]
        measured = run_metrics(run, objects, negative=negative)
        errors = {}
        if negative:
            require(all(task.get(field) is None for field in
                        ('final_position_error_m', 'zone_a_error_m', 'zone_b_error_m')),
                    'negative case invents a placement metric')
        elif case == 'dual_object':
            errors = {name: number(task.get(field), field) for name, field in
                      [('target_box_a', 'zone_a_error_m'), ('target_box_b', 'zone_b_error_m')]}
        else:
            errors = {obj: number(task.get('final_position_error_m'), 'task placement error')}
        for name, error in errors.items():
            require(error <= measured['verify_tolerance_m'], 'placement error exceeds actual verifier tolerance')
            require(math.isclose(error, measured['object_errors_m'][name], rel_tol=1e-9, abs_tol=1e-12),
                    'task and verifier placement metrics disagree')
        result.append(dict(case=case, object=obj, status=outcome['status'],
                           outcome=task['outcome'], error_code=task['error_code'],
                           expectation_met=True, task_error_m=None if negative or case == 'dual_object' else errors[obj],
                           zone_errors_m=errors if case == 'dual_object' else None, **measured))
    return result


def compare(paths, *, max_placement_error_m=None, expected_cases=5):
    require(len(paths) >= 2, 'parity needs at least two backends')
    require(type(expected_cases) is int and expected_cases == 5, 'the declaration has five cases')
    windows = [(Path(path).parent.name, load(path), Path(path).parent) for path in paths]
    require(len({Path(path).resolve() for path in paths}) == len(paths), 'duplicate window path')
    require(len({name for name, _, _ in windows}) == len(windows), 'duplicate report table identity')
    require(len({window['backend'] for _, window, _ in windows}) == len(windows), 'duplicate carry backend')
    require(len({window['skill_backend'] for _, window, _ in windows}) == 1, 'different skill backends cannot be compared')
    digests = {window['declaration_sha256'] for _, window, _ in windows}
    require(len(digests) == 1, 'the windows were not declared from the same manifest')
    for name, window, _ in windows:
        require(len(window['episodes']) == 5, '%s did not run the declared number of cases' % name)
        require([(e['case'], e['object']) for e in window['episodes']] == CASES, 'different case list from declaration')
    table, tolerances = {}, set()
    for name, window, base in windows:
        measured = case_rows(window, base)
        table[name] = dict(status=window['status'], backend=window['backend'], cases=measured)
        tolerances.update(row['verify_tolerance_m'] for row in measured if row['case'] != 'budget_exhaustion')
    require(len(tolerances) == 1, 'the backends were verified against different tolerances')
    tolerance = tolerances.pop()
    if max_placement_error_m is not None:
        require(number(max_placement_error_m, 'requested tolerance', positive=True) == tolerance,
                'requested tolerance differs from actual verify receipts')
    return dict(status='CARRY_BACKEND_PARITY_PASS', declaration_sha256=digests.pop(),
                skill_backend=windows[0][1]['skill_backend'],
                backends={name: value['backend'] for name, value in table.items()},
                cases=[dict(case=c, object=o) for c, o in CASES], table=table,
                declared_tolerance_m=tolerance, max_placement_error_m=tolerance,
                max_verified_error_m={name: max(r['verify_error_m'] for r in value['cases']
                                              if r['verify_error_m'] is not None) for name, value in table.items()},
                attempts={name: {r['case']+'/'+r['object']: r['pick_attempts'] for r in value['cases']}
                          for name, value in table.items()}, tolerance_moved=False, default_admission='NO_GO',
                interpretation='Same declared cases, skill backend and actual verifier tolerance; '
                               'one bounded window per carry backend, not a success rate or legacy/D3 admission')


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('windows', nargs='+', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    text = json.dumps(compare(args.windows), indent=2, allow_nan=False)
    if args.out: args.out.write_text(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
