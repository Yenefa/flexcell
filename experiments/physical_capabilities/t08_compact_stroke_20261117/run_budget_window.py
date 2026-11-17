"""Run the fixed push budget comparison and ordinary smoke regressions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import jsonschema

ROOT = Path('/candidate')
IMAGE = Path('/opt/flexcell/repo')
HERE = Path(__file__).resolve().parent
HISTORY = ROOT / 'setup/acceptance/evobot_runtime_push_20261112'
ORIGINAL = ROOT / 'benchmark/tasks/t08_dev/T08-push-seed2000.json'
sys.path.insert(0, str(HERE.parent / 't08_reachable_contact_20261113'))
from run_window import ordinary_result, production_hashes, read, unknown

sys.path.insert(0, str(HISTORY))
from ci_window import FROZEN, prepare


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def push_result(directory, slot, task, exit_code):
    spec = read(task)
    target = next(iter(spec['expected_goal']['push']))
    before, after = (read(directory / name) for name in ('gt_before.json', 'gt_after.json'))
    net = before['objects'][target][0] - after['objects'][target][0] if before and after else None
    runtime = read(directory / 'runtime/runtime_result.json')
    decision = read(directory / 'runtime/decision.json')
    verdict = read(directory / 'verdict.json')
    provenance = read(directory / 'provenance.json') or {}
    components = [read(path) for path in sorted(directory.glob('contact_goals/*/action_result.json'))]
    observed = (runtime or {}).get('runtime_result') or {}
    finished = observed.get('completed_stage_ids') or []
    stage_count = 2 if slot['task'] == 'original' else 3
    used = sum(c['motion_goals_used'] for c in components) if all(components) else None
    gates = (verdict or {}).get('evidence', {}).get('gates', [])
    cap = slot['goal_limit']
    budget = spec['execution_budget']
    if slot['expected'] == 'BUDGET_REFUSAL':
        qualified = bool(exit_code == 0 and runtime and runtime['status'] == 'FAILED'
                         and runtime.get('detail','').startswith('PushTaskRejected:')
                         and 'budget' in runtime['detail'] and decision is None and not components
                         and not finished and net is not None and abs(net) <= .001
                         and verdict and verdict['passed'] is False)
    else:
        qualified = bool(exit_code == 0 and runtime and runtime['agent_claimed_success'] is True
                         and runtime['status'] == 'TASK_COMPLETED' and runtime['wall_s'] <= budget['max_wall_s']
                         and decision and decision['capabilities']['push_motion_goal_limit'] == cap
                         and verdict and verdict['passed'] is True and len(gates) == 9
                         and all(gate['ok'] is True for gate in gates) and len(finished) == stage_count
                         and len(components) == stage_count and all(components) and used <= budget['max_steps']
                         and all(c['arm_ready'] is True and c['return_completed'] is True
                                 and c['motion_terminal_known'] is True and c['motion_goals_used'] <= cap
                                 for c in components))
    return dict(driver_exit=exit_code, expected=slot['expected'], qualified=qualified,
                task_sha256=digest(task), world_sha256=provenance.get('world_sha256'),
                status=read(directory / 'run_status.json'), runtime=runtime, verdict=verdict,
                components=components, stages_completed=len(finished), motion_goals_used=used,
                net_signed_m=net, unknown_terminal=unknown([runtime, components]))


def main():
    out = Path('/artifacts')
    config, freeze = (read(HERE / name) for name in ('preregistration.json', 'source_freeze.json'))
    schema = read(HERE.parent / 't08_position_contact_20261113/probe.schema.json')
    jsonschema.validate(read(HERE / 'budget30.json'), schema)
    before = production_hashes(ROOT)
    for root in (ROOT, IMAGE):
        for path, expected in {**freeze['sha256'], **FROZEN}.items():
            if digest(root / path) != expected:
                raise RuntimeError('fixed experiment input changed: ' + path)
    dump(out / 'frozen_integrity.json', FROZEN)
    dump(out / 'preexecution.json', dict(config=config, source_revision=os.environ['FLEXCELL_SOURCE_REV'],
                                         model=prepare(out / 'model'), sources=before, freeze=freeze,
                                         model_calls=0))
    rows = []
    started = time.monotonic()
    stopped = None
    all_qualified = False
    try:
        for slot in config['slots']:
            label = slot['id']
            is_push = 'task' in slot
            timeout = config['push_timeout_s' if is_push else 'ordinary_timeout_s']
            row = dict(label=label, kind='push' if is_push else 'ordinary', expected=slot['expected'])
            rows.append(row)
            if stopped or time.monotonic() - started + timeout > config['window_budget_s']:
                row.update(status='NOT_RUN', reason=stopped or 'window budget', qualified=False)
                continue
            directory = out / label
            if is_push:
                task = ORIGINAL if slot['task'] == 'original' else HERE / slot['task']
                argv = [sys.executable, str(HERE / 'run_case.py'), 'finger_tcp', label,
                        str(slot['domain']), str(task), str(slot['goal_limit'])]
            else:
                argv = [sys.executable, str(ROOT / 'scripts/sim_smoke.py'), '--out', str(directory),
                        '--case', slot['case'], '--backend', 'velocity_servo', '--skill-backend', 'legacy']
            env = dict(os.environ, ROS_DOMAIN_ID=str(slot['domain']), GZ_PARTITION='compact-' + label)
            with (out / (label + '_driver.log')).open('x') as log:
                try:
                    exit_code = subprocess.run(argv, env=env, stdout=log, stderr=subprocess.STDOUT,
                                               timeout=timeout).returncode
                except subprocess.TimeoutExpired:
                    stopped = 'outer timeout; unknown terminal'
                    exit_code = 124
            try:
                if is_push:
                    row.update(push_result(directory, slot, task, exit_code))
                else:
                    result, path = ordinary_result(directory, slot['case'])
                    row.update(driver_exit=exit_code, result=result, result_path=str(path),
                               qualified=exit_code == 0 and result['status'] == 'PASS',
                               unknown_terminal=unknown(result))
            except (ValueError, KeyError, TypeError) as exc:
                row.update(qualified=False, driver_exit=exit_code, error=str(exc), unknown_terminal=True)
            if row.get('unknown_terminal') or row.get('runtime') is None and is_push:
                stopped = stopped or 'unknown or unavailable task terminal'
            print('PHYSICAL_SLOT ' + json.dumps({key: row.get(key) for key in (
                'label','qualified','motion_goals_used','net_signed_m','stages_completed','error')},
                allow_nan=False), flush=True)
            dump(out / 'results.partial.json', rows)
        compared = rows[:3]
        same_case = (len({r.get('task_sha256') for r in compared}) == 1
                     and len({r.get('world_sha256') for r in compared}) == 1
                     and all(r.get('world_sha256') for r in compared))
        all_qualified = same_case and all(row.get('qualified') for row in rows) and not stopped
    finally:
        unchanged = production_hashes(ROOT) == before
        dump(out / 'results.json', dict(source_revision=os.environ['FLEXCELL_SOURCE_REV'], results=rows,
                                       source_unchanged=unchanged, stop_reason=stopped,
                                       all_slots_qualified=bool(all_qualified and unchanged),
                                       formal_held_out=False, baseline_promoted=False))
        manifest = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*'))
                    if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
        dump(out / 'SHA256_MANIFEST.json', manifest)
    return 0 if all_qualified and unchanged else 2


if __name__ == '__main__':
    raise SystemExit(main())
