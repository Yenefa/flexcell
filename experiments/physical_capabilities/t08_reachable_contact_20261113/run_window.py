"""Frozen implementation tested on predeclared position and contact probes."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/candidate')
HERE = Path(__file__).resolve().parent
HISTORY = ROOT / 'setup/acceptance/evobot_runtime_push_20261112'


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return None


def unknown(value):
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



def ordinary_result(directory, expected_case):
    paths = list(Path(directory).glob('run-*/result.json'))
    if len(paths) != 1:
        raise ValueError('ordinary result requires exactly one run directory')
    result = read(paths[0])
    if not isinstance(result, dict) or result.get('case') != expected_case:
        raise ValueError('ordinary result case differs from declared slot')
    return result, paths[0]


def production_hashes(root):
    paths = list((root / 'src/flexcell').rglob('*.py'))
    paths += list((root / 'src/flexcell/flexcell_interfaces').rglob('*.action'))
    paths += list((root / 'src/flexcell/flexcell_interfaces').rglob('*.msg'))
    paths += list((root / 'runtime').rglob('*.py'))
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    out = Path('/artifacts')
    out.mkdir(exist_ok=True)
    config = read(HERE / 'preregistration.json')
    import jsonschema
    for slot in config['push_slots']:
        if slot['task'] != 'original':
            jsonschema.validate(read(HERE / slot['task']), read(HERE / 'probe.schema.json'))
    freeze = read(HERE / 'source_freeze.json')
    for root in (ROOT, Path('/opt/flexcell/repo')):
        for path, digest in freeze['sha256'].items():
            if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
                raise RuntimeError('implementation changed after probe declaration: ' + path)
    sys.path.insert(0, str(HISTORY))
    from prepare_model import prepare
    tree = ast.parse((HISTORY / 'ci_window.py').read_text())
    frozen = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'FROZEN' for t in n.targets))
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in frozen}
    if hashes != frozen:
        raise RuntimeError('frozen contract or push arithmetic differs')
    (out / 'frozen_integrity.json').write_text(json.dumps(hashes, indent=2))
    model = prepare(out / 'model')
    before = production_hashes(ROOT)
    metadata = dict(config=config, source_revision=os.environ.get('FLEXCELL_SOURCE_REV'),
                    model=model, sources=before, freeze=freeze, model_calls=0,
                    source_policy='Candidate frozen before this repair window; task already exposed and original failure retained.')
    (out / 'preexecution.json').write_text(json.dumps(metadata, indent=2))
    rows = []
    started = time.monotonic()
    stopped = None
    slots = [(s, 'push') for s in config['push_slots']] + [(s, 'ordinary') for s in config['ordinary_slots']]
    try:
        for slot, kind in slots:
            label = slot['label']
            timeout = config['push_timeout_s'] if kind == 'push' else config['ordinary_timeout_s']
            if stopped or time.monotonic() - started + timeout > config['window_budget_s']:
                rows.append(dict(label=label, kind=kind, status='NOT_RUN', reason=stopped or 'window budget'))
                continue
            if kind == 'push':
                task = slot['task'] if slot['task'] == 'original' else str(HERE / slot['task'])
                argv = [sys.executable, str(HISTORY / 'run_case.py'), 'finger_tcp', label, str(slot['domain']), task]
            else:
                argv = [sys.executable, str(ROOT / 'scripts/sim_smoke.py'), '--out', str(out / label),
                        '--case', slot['case'], '--backend', 'velocity_servo', '--skill-backend', 'legacy']
            env = dict(os.environ, ROS_DOMAIN_ID=str(slot['domain']), GZ_PARTITION='physical-' + label)
            with (out / (label + '_driver.log')).open('x') as log:
                try:
                    process = subprocess.run(argv, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    exit_code = 124
                    stopped = 'outer timeout; action terminal requires reconciliation'
            directory = out / label
            if kind == 'push':
                status = read(directory / 'run_status.json')
                verdict = read(directory / 'verdict.json')
                runtime = read(directory / 'runtime/runtime_result.json')
                components = [read(p) for p in directory.glob('contact_goals/*/action_result.json')]
                gates = (verdict or {}).get('evidence', {}).get('gates', [])
                passed = bool(exit_code == 0 and runtime and runtime.get('agent_claimed_success') is True
                              and verdict and verdict.get('passed') is True
                              and len(gates) == 9 and all(g['ok'] for g in gates))
                row = dict(label=label, kind=kind, driver_exit=exit_code, task_completed=passed,
                           status=status, runtime=runtime, independent_verdict=verdict, components=components)
                start = read(directory / 'gt_before.json')
                end = read(directory / 'gt_after.json')
                spec_path = ROOT / 'benchmark/tasks/t08_dev/T08-push-seed2000.json' if slot['task'] == 'original' else HERE / slot['task']
                spec = read(spec_path)
                target = next(iter(spec['expected_goal']['push']))
                row['task_id'] = spec['task_id']
                row['task_sha256'] = hashlib.sha256(spec_path.read_bytes()).hexdigest()
                if start and end:
                    row['net_signed_m'] = start['objects'][target][0] - end['objects'][target][0]
                if unknown([runtime, components]):
                    stopped = 'unknown executed motion terminal'
            else:
                result, result_path = ordinary_result(directory, slot['case'])
                row = dict(label=label, kind=kind, driver_exit=exit_code, result=result, result_path=str(result_path),
                           task_completed=bool(exit_code == 0 and result and result.get('status') == 'PASS'))
                if unknown(result):
                    stopped = 'unknown ordinary-task motion terminal'
            rows.append(row)
            print('PHYSICAL_SLOT ' + json.dumps({k: row.get(k) for k in
                ('label', 'kind', 'driver_exit', 'task_completed', 'net_signed_m')}), flush=True)
            (out / 'results.partial.json').write_text(json.dumps(rows, indent=2))
    finally:
        unchanged = production_hashes(ROOT) == before
        payload = dict(experiment=config['experiment'], source_revision=metadata['source_revision'],
                       results=rows, source_unchanged=unchanged, stop_reason=stopped,
                       all_tasks_completed=len(rows) == len(slots) and all(r.get('task_completed') for r in rows),
                       baseline_promoted=False, formal_held_out=False)
        (out / 'results.json').write_text(json.dumps(payload, indent=2))
        manifest = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in out.rglob('*') if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
        (out / 'SHA256_MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    return 0 if payload['all_tasks_completed'] and unchanged else 2


if __name__ == '__main__':
    raise SystemExit(main())
