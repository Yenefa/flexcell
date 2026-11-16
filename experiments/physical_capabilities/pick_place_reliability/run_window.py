#!/usr/bin/env python3
"""Fixed four-slot pick/place window (physical capability C).

Scope: FUNCTIONAL_SMOKE_ONLY. Reuses the existing sim_smoke entrypoint and the
original `normal` / `dual_object` cases without changing objects, targets,
tolerances or task budgets. Keeps every failure; stops the window on an unknown
terminal state instead of dispatching another goal.

Run: python3 experiments/physical_capabilities/pick_place_reliability/run_window.py \
        --out /artifacts/pick-place
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def _repo_root():
    """Locate the repository without assuming a fixed directory depth."""
    env = os.environ.get('FLEXCELL_REPO')
    if env:
        return Path(env)
    for candidate in HERE.parents:
        if (candidate / 'src/flexcell').is_dir():
            return candidate
    return Path.cwd()


ROOT = _repo_root()
DEFAULT_PREREG = HERE / 'preregistration.json'


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def unknown(value):
    """Recursively detect an unknown terminal state: missing evidence is UNKNOWN."""
    if isinstance(value, dict):
        if (value.get('status') in ('STATE_UNKNOWN', 'ACTION_TERMINAL_UNKNOWN')
                or value.get('motion_terminal_known') is False
                or value.get('terminal_known') is False
                or value.get('error_code') == 33):
            return True
        return any(unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(unknown(v) for v in value)
    if isinstance(value, str) and value.startswith(('{', '[')):
        try:
            return unknown(json.loads(value))
        except ValueError:
            pass
    return False


def one_result(directory, expected_case):
    """Exactly one run-* directory whose case matches the declared slot."""
    paths = list(Path(directory).glob('run-*/result.json'))
    if len(paths) != 1:
        raise ValueError('expected exactly one run-* result, found %d' % len(paths))
    result = read(paths[0])
    if not isinstance(result, dict):
        raise ValueError('unreadable result: %s' % paths[0])
    if result.get('case') != expected_case:
        raise ValueError('case %r != declared %r' % (result.get('case'), expected_case))
    return result, paths[0]


def source_hashes():
    paths = list((ROOT / 'src/flexcell').rglob('*.py'))
    paths += list((ROOT / 'src/flexcell/flexcell_interfaces').rglob('*.action'))
    paths += list((ROOT / 'src/flexcell/flexcell_interfaces').rglob('*.msg'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def slot_command(label, case, slot_out, backend, skill_backend):
    return [sys.executable, str(ROOT / 'scripts/sim_smoke.py'),
            '--out', str(slot_out), '--case', case,
            '--backend', backend, '--skill-backend', skill_backend]


def slot_env(label, index):
    """Per-slot ROS/Gazebo isolation: a leftover graph must not leak into the next slot."""
    return dict(os.environ, ROS_DOMAIN_ID=str(51 + index), GZ_PARTITION='pp-' + label)


def classify(result, exit_code):
    if exit_code == 124:
        return 'UNKNOWN'
    if unknown(result):
        return 'UNKNOWN'
    if exit_code == 0 and result.get('status') == 'PASS':
        return 'OK'
    return 'TASK_FAILED'


def run_window(prereg, out, runner=None):
    """Execute the declared slots. runner(label, case, slot_out, index) -> exit_code."""
    slots = prereg['slots']
    slot_timeout = float(prereg['slot_timeout_s'])
    budget = float(prereg['window_budget_s'])
    backend = prereg['backend']
    skill_backend = prereg['skill_backend']
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    before = source_hashes()
    rows = []
    started = time.monotonic()
    stopped = None

    for index, slot in enumerate(slots):
        label, case = slot['label'], slot['case']
        if stopped:
            rows.append(dict(label=label, case=case, status='NOT_RUN', reason=stopped))
            continue
        if time.monotonic() - started + slot_timeout > budget:
            rows.append(dict(label=label, case=case, status='NOT_RUN', reason='window budget'))
            continue

        slot_out = out / label
        if runner is None:
            argv = slot_command(label, case, slot_out, backend, skill_backend)
            with (out / (label + '_driver.log')).open('x') as log:
                try:
                    proc = subprocess.run(argv, env=slot_env(label, index), stdout=log,
                                          stderr=subprocess.STDOUT, timeout=slot_timeout)
                    exit_code = proc.returncode
                except subprocess.TimeoutExpired:
                    exit_code = 124
                    stopped = 'outer timeout; action terminal requires reconciliation'
        else:
            exit_code = runner(label, case, slot_out, index)

        row = dict(label=label, case=case, driver_exit=exit_code, status='UNKNOWN')
        try:
            result, result_path = one_result(slot_out, case)
            task = result.get('task') or {}
            row.update(result_path=str(result_path),
                       harness_status=result.get('status'),
                       outcome=task.get('outcome'),
                       error_code=task.get('error_code'),
                       wall_seconds=task.get('wall_seconds'),
                       err_m=task.get('final_position_error_m'),
                       task_completed=(exit_code == 0 and result.get('status') == 'PASS'))
            row['status'] = classify(result, exit_code)
            if row['status'] == 'UNKNOWN' and not stopped:
                stopped = 'unknown terminal state in %s' % label
        except ValueError as exc:
            row['status'] = 'UNKNOWN'
            row['error'] = str(exc)
            if not stopped:
                stopped = 'unknown terminal state in %s (%s)' % (label, exc)

        rows.append(row)
        (out / 'results.partial.json').write_text(
            json.dumps(rows, indent=2, ensure_ascii=False))

    after = source_hashes()
    payload = dict(
        experiment=prereg.get('experiment'),
        scope='FUNCTIONAL_SMOKE_ONLY',
        results=rows,
        source_unchanged=(before == after),
        stop_reason=stopped,
        all_slots_completed=(len(rows) == len(slots) and all(r.get('task_completed') for r in rows)),
        baseline_promoted=False,
    )
    (out / 'results.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    manifest = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out.rglob('*') if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
    (out / 'SHA256_MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--preregistration', type=Path, default=DEFAULT_PREREG)
    args = parser.parse_args(argv)

    prereg = read(args.preregistration)
    if not isinstance(prereg, dict) or not prereg.get('slots'):
        raise SystemExit('invalid preregistration: %s' % args.preregistration)
    payload = run_window(prereg, args.out)
    print('WINDOW ' + json.dumps(dict(
        all_slots_completed=payload['all_slots_completed'],
        source_unchanged=payload['source_unchanged'],
        stop_reason=payload['stop_reason']), ensure_ascii=False))
    return 0 if payload['all_slots_completed'] and payload['source_unchanged'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
