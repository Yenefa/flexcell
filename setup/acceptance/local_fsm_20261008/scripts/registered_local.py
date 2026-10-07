#!/usr/bin/env python3
"""Run only the fixed local FSM prefix; retain the previous zero-claim stop."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WS = Path('/home/ros/agentic_workcell_ws')
LOG = Path('/home/ros/fc_sync_logs/local_fsm_20261007')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import bounded_runner as engine
import qualification_prepare as q
import t1_pilot as base

readiness = base.module('local_fsm_readiness', WS / 'setup/131_prebatch_readiness.py')
SHA = '3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f'


def command(name, args, timeout=1200):
    path = ROOT / 'validation' / (name + '.log')
    started = time.perf_counter_ns()
    with path.open('x') as stream:
        try:
            proc = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = None
    value = dict(argv=args, return_code=rc, stdout_stderr_combined=path.read_text(),
                 elapsed_ms=(time.perf_counter_ns() - started)/1e6)
    engine.write(ROOT / 'validation' / (name + '.json'), value)
    return value


def first():
    (ROOT / 'validation').mkdir(exist_ok=False)
    local = command('preswitch_health_attempt01', [sys.executable, str(WS / 'setup/flexcell_admin.py'), 'health'], 75)
    readiness.confirmed_health(dict(return_code=local['return_code'], stdout=local['stdout_stderr_combined']))
    switch = command('activate_fsm_attempt01', ['bash', str(WS / 'setup/102_mainline_runtime.sh'), 'switch', 'fsm', '0.85'], 180)
    q.require(type(switch['return_code']) is int and switch['return_code'] == 0, 'FSM activation unconfirmed; no tasks allowed')
    deployment = sorted(base.RUNTIME.glob('*/deployment.json'))[-1]
    data = q.loads(deployment.read_bytes())
    identity = q.loads((WS / 'setup/acceptance/qualification_inputs_20261007/inputs/identity.json').read_bytes())
    q.require(data['policy'] == 'fsm' and data['runtime_fingerprint'] == identity['proposed_runtime_fingerprints']['fsm'], 'FSM fingerprint drift')
    ready = command('fsm_readiness_attempt01', [sys.executable, str(WS / 'setup/131_prebatch_readiness.py'),
        '--live', '--workspace', str(WS), '--deployment', str(deployment),
        '--receipt', str(WS / 'setup/acceptance/bounded_runner_20261007'),
        '--out', str(ROOT / 'validation/fsm_readiness_report.json')], 85)
    q.require(type(ready['return_code']) is int and ready['return_code'] == 0, 'strict local readiness failed')
    report = q.loads((ROOT / 'validation/fsm_readiness_report.json').read_bytes())
    q.require(report['read_only_preflight_ok'] is True
        and report['checks']['live_readonly']['active_policy'] == 'fsm'
        and report['checks']['live_readonly']['model_routes_required'] is False, 'FSM must be measured active without model dependencies')
    revision = q.loads((LOG / 'code_commit.json').read_bytes())['head']
    cli = [sys.executable, str(WS / 'setup/133_bounded_runner.py')]
    register = command('register_attempt01', cli + ['register',
        '--package', str(WS / 'setup/acceptance/qualification_inputs_20261007/inputs'),
        '--expected-sha256', SHA, '--order', 'local-first',
        '--predecessor', str(WS / 'setup/acceptance/bounded_runner_20261007/run'),
        '--out', str(ROOT / 'run'), '--history', str(base.LOGS / 'episodes'),
        '--budget', os.environ['FLEXCELL_LLM_BUDGET_FILE'], '--revision', revision])
    q.require(register['return_code'] == 0, 'registration failed; retain evidence')
    before = q.sha(ROOT / 'run/events.jsonl')
    dry = command('default_readonly_attempt01', cli + ['run', '--root', str(ROOT / 'run')])
    q.require(dry['return_code'] == 0 and q.sha(ROOT / 'run/events.jsonl') == before, 'default run must remain read-only')
    execute = command('first_fsm_attempt01', cli + ['run', '--root', str(ROOT / 'run'), '--execute', '--max-slots', '1'])
    state = engine.status(ROOT / 'run', WS)
    engine.write(ROOT / 'validation/first_fsm_status.json', dict(state, execution_return_code=execute['return_code']))
    print(json.dumps(state), flush=True)
    return 0 if state['state'] == 'PAUSED' and state['completed_slots'] == 1 else 2


def resume():
    state = engine.status(ROOT / 'run', WS)
    q.require(state['state'] == 'PAUSED' and state['completed_slots'] == 1, 'only the owned committed first-slot boundary may resume')
    execute = command('remaining_fsm_attempt01', [sys.executable, str(WS / 'setup/133_bounded_runner.py'),
        'run', '--root', str(ROOT / 'run'), '--execute', '--max-slots', '2'])
    final = engine.status(ROOT / 'run', WS)
    engine.write(ROOT / 'validation/local_final_status.json', dict(final, execution_return_code=execute['return_code']))
    print(json.dumps(final), flush=True)
    return 0 if final['state'] == 'PAUSED' and final['completed_slots'] == 3 else 2


if __name__ == '__main__':
    q.require(len(sys.argv) == 2 and sys.argv[1] in ('first', 'resume'), 'explicit phase required')
    raise SystemExit(first() if sys.argv[1] == 'first' else resume())
