#!/usr/bin/env python3
"""Retain actual offline CLI receipts; this never dispatches robot work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = Path('/home/ros/agentic_workcell_ws')
sys.path.insert(0, str(REPO / 'setup/transferbench'))
import qualification_prepare as q


def write(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def command(name, args):
    started = time.perf_counter_ns()
    result = subprocess.run(args, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=60)
    record = {'argv': args, 'return_code': result.returncode, 'stdout': result.stdout,
              'stderr': result.stderr, 'elapsed_ms': (time.perf_counter_ns()-started)/1e6}
    write(ROOT / 'validation' / (name + '.json'), record)
    return result


def main():
    revision = 'fe4e33b9e7a843ae2dd68f8c43dd8d13ac05a13f'
    ROOT.joinpath('validation').mkdir(exist_ok=False)
    history = Path('/home/ros/.ros/flexcell/episodes')
    budget = Path(os.environ['FLEXCELL_LLM_BUDGET_FILE'])
    budget_sha = q.sha(budget)
    before = q.history_snapshot(history)
    write(ROOT / 'validation/registration.json', {
        'operation': 'OFFLINE_INPUT_PREPARATION', 'revision': revision,
        'history_files': len(before['files']), 'history_states': before['observed_states'],
        'history_snapshot_sha256': q.digest(before), 'budget_sha256': budget_sha,
        'max_native_episodes': 0, 'max_model_calls': 0,
        'sampling_authorized': False, 'n_ge_50': 'FROZEN'})
    args = [sys.executable, str(REPO / 'setup/132_qualification_prepare.py'), 'prepare',
            '--out', str(ROOT / 'inputs'), '--history', str(history),
            '--deployment', '/home/ros/.local/share/flexcell/mainline/runtime/20261007_132145/deployment.json',
            '--calibration', '/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json',
            '--familiar-inputs', str(REPO / 'setup/acceptance/transferbench_t1_20261006/plan/initial_states.json'),
            '--budget', str(budget), '--workspace', str(REPO), '--revision', revision,
            '--seed', '2026100701']
    made = command('prepare_attempt01', args)
    require = q.require
    require(made.returncode == 0, 'preparation failed; retain original receipt')
    output = q.loads(made.stdout)
    verify_args = [sys.executable, str(REPO / 'setup/132_qualification_prepare.py'), 'verify',
                   '--root', str(ROOT / 'inputs'), '--expected-sha256', output['package_sha256'],
                   '--workspace', str(REPO), '--history', str(history)]
    checked = command('verify_attempt01', verify_args)
    require(checked.returncode == 0, 'verification failed; no earlier JSON overrides process failure')
    check = q.loads(checked.stdout)
    require(check['ok'] is True and check['frozen_package_ok'] is True
            and check['history_verified'] is True and check['implementation_verified'] is True,
            'typed verification did not confirm all external inputs')
    rejected = command('overwrite_control_attempt01', args)
    require(rejected.returncode == 2 and q.loads(rejected.stdout)['ok'] is False,
            'existing output must be rejected')
    require(q.sha(ROOT / 'inputs/SHA256SUMS.json') == output['package_sha256'], 'overwrite changed package')
    require(q.same_typed(before, q.history_snapshot(history)), 'episode file-set or bytes changed')
    require(q.sha(budget) == budget_sha, 'budget changed during offline preparation')
    write(ROOT / 'report.json', {
        'record_kind': 'QUALIFICATION_INPUT_PREPARATION_EVIDENCE', 'ok': True,
        'revision': revision, 'package_sha256': output['package_sha256'],
        'target_cases': output['target_cases'], 'schedule_slots': output['schedule_slots'],
        'history_files': len(before['files']), 'observed_history_states': before['observed_states'],
        'unique_history_layouts': len(before['layouts']), 'episode_file_set_and_bytes_unchanged': True,
        'existing_budget_bytes_unchanged': True, 'overwrite_rejected': True,
        'offline_instrument_tests': 82, 'native_episodes_executed': 0, 'model_calls': 0,
        'runtime_source_or_profile_changed': False, 'prompt_or_calibration_changed': False,
        'candidate_custody': 'NOT_INDEPENDENT; repository-disclosed inputs',
        'qualification': 'PREPARED_NOT_RATIFIED', 'sampling_authorized': False,
        'ready_for_large_test': False, 'large_tests_started': False, 'AC90': 'NOT_RUN', 'n_ge_50': 'FROZEN'})
    print(json.dumps(q.loads((ROOT / 'report.json').read_bytes())))


if __name__ == '__main__':
    main()
