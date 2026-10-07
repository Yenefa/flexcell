#!/usr/bin/env python3
"""Register once, run two T1 slots, and retain the actual pause boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WS = Path('/home/ros/agentic_workcell_ws')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import bounded_runner as engine
import qualification_prepare as q


def command(name, args, timeout=1800):
    log = ROOT / 'validation' / (name + '.log')
    started = time.perf_counter_ns()
    with log.open('x') as f:
        proc = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    result = {'argv': args, 'return_code': proc.returncode, 'stdout_stderr_combined': log.read_text(),
              'elapsed_ms': (time.perf_counter_ns()-started)/1e6}
    engine.write(ROOT / 'validation' / (name + '.json'), result)
    return proc.returncode


def main():
    (ROOT / 'validation').mkdir(exist_ok=False)
    revision = '2e17ac9ad9af333fb1410ebdaf54258b97e58a3c'
    cli = [sys.executable, str(WS / 'setup/133_bounded_runner.py')]
    register = cli + ['register', '--package', str(WS / 'setup/acceptance/qualification_inputs_20261007/inputs'),
        '--expected-sha256', '3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f',
        '--out', str(ROOT / 'run'), '--history', '/home/ros/.ros/flexcell/episodes',
        '--budget', os.environ['FLEXCELL_LLM_BUDGET_FILE'], '--revision', revision]
    q.require(command('register_attempt01', register) == 0, 'registration failed; preserve receipt')
    before = q.sha(ROOT / 'run/events.jsonl')
    q.require(command('default_readonly_attempt01', cli + ['run', '--root', str(ROOT / 'run')]) == 0, 'default dry-run failed')
    q.require(q.sha(ROOT / 'run/events.jsonl') == before, 'default run changed the journal')
    rc = command('prefix_execute_attempt01', cli + ['run', '--root', str(ROOT / 'run'), '--execute', '--max-slots', '2'])
    status = engine.status(ROOT / 'run', WS)
    engine.write(ROOT / 'validation/prefix_status.json', dict(status, execution_return_code=rc))
    print(json.dumps(status), flush=True)
    q.require(rc == 0 and status['state'] == 'PAUSED' and status['completed_slots'] == 2,
              'registered prefix stopped; never resubmit completed or failed goals')


if __name__ == '__main__':
    main()
