"""Offline real-input prepare/verify; preserve the negative overwrite attempt."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
LOG = Path('/home/ros/fc_sync_logs/qualification_private_development_20261008')
ROOT = WS / 'setup/acceptance/qualification_private_20261008'
PRIVATE = Path('/home/ros/fc_sync_logs/qualification_private_20261008/inputs')
ACTIVE = Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q
import bounded_runner as engine

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(q.encoded(value))

q.require(not ROOT.exists() and not PRIVATE.exists(), 'preserve existing receipt or private output')
code = q.loads((LOG / 'code_commit.json').read_bytes())
before = q.loads((LOG / 'before.json').read_bytes())
common = ['--workspace', str(WS), '--history', '/home/ros/.ros/flexcell/episodes',
          '--calibration', '/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json',
          '--budget', '/home/ros/.config/flexcell/deepseek_budget_20261001.json']
prepare = ['prepare', '--out', str(PRIVATE), '--commitment', str(ROOT / 'commitment.json'),
           '--published', str(WS / 'setup/acceptance/qualification_inputs_20261007/inputs'),
           '3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f',
           '--deployment', '/home/ros/.local/share/flexcell/mainline/runtime/20261007_132145/deployment.json',
           '--familiar-inputs', str(WS / 'setup/acceptance/transferbench_t1_20261006/plan/initial_states.json'),
           '--revision', code['head'], *common]

def call(name, arguments, expected_code):
    argv = [sys.executable, str(WS / 'setup/134_qualification_private.py'), *arguments]
    result = subprocess.run(argv, cwd=WS, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    value = {'argv': argv, 'cwd': str(WS), 'return_code': result.returncode,
             'stdout': result.stdout.decode(), 'stderr': result.stderr.decode()}
    write(ROOT / 'validation' / (name + '.json'), value)
    q.require(result.returncode == expected_code, 'unexpected or signaled CLI outcome; preserve attempt')
    payload = q.loads(result.stdout)
    q.require(type(payload.get('ok')) is bool and payload['ok'] is (expected_code == 0), 'typed CLI result required')
    return payload

made = call('prepare_attempt01', prepare, 0)
verified = call('verify_attempt01', ['verify', '--commitment', str(ROOT / 'commitment.json'),
                   '--expected-sha256', made['commitment_sha256'], *common], 0)
q.require(q.same_typed(made, verified), 'prepare/verify metadata differs')
rejected = call('overwrite_refusal_attempt01', prepare, 2)
q.require('already exists' in rejected['error'], 'negative attempt was not overwrite refusal')
q.require(q.sha(ROOT / 'commitment.json') == made['commitment_sha256'] and
          q.sha(PRIVATE / 'SHA256SUMS.json') == made['private_package_sha256'], 'negative attempt changed artifact')
state = engine.status(ACTIVE, WS)
plan, _, _, _, _ = engine.read(ACTIVE, WS)
active_pins = {str(p.relative_to(ACTIVE)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
               for p in sorted(ACTIVE.rglob('*')) if p.is_file()}
history = q.history_snapshot(Path(plan['history_path']))
q.require(q.digest(active_pins) == before['collector_tree_sha256'] and
          q.same_typed(state, before['collector_status']) and
          q.same_typed(plan['executor_sha256'], before['collector_source_sha256']), 'collector mutated')
q.require(q.digest(history) == before['history_sha256'] and len(history['files']) == 374,
          'history changed; do not pool or rewrite')
q.require(q.sha(Path(plan['budget_path'])) == before['budget_sha256'], 'budget changed')
q.require(q.sha(Path(common[common.index('--calibration') + 1])) == before['calibration_sha256'],
          'calibration changed')
for rel, old in before['old_evidence_seals'].items():
    base = WS / rel
    q.require(q.sha(base / 'SHA256SUMS.json') == old['seal_sha256'], 'old seal changed')
    for name, pin in q.loads((base / 'SHA256SUMS.json').read_bytes()).items():
        path = q.regular(base, name)
        q.require(pin['sha256'] == q.sha(path) and pin['bytes'] == path.stat().st_size, 'old receipt changed')
write(ROOT / 'validation/after.json', {
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'collector_status': state,
    'collector_tree_sha256': q.digest(active_pins), 'collector_unchanged': True,
    'collector_source_sha256': plan['executor_sha256'], 'history_sha256': q.digest(history),
    'history_files': len(history['files']), 'history_unchanged': True,
    'budget_sha256': before['budget_sha256'], 'budget_unchanged': True,
    'calibration_sha256': before['calibration_sha256'], 'calibration_unchanged': True,
    'old_evidence_seals': before['old_evidence_seals'], 'old_evidence_unchanged': True})
write(ROOT / 'report.json', {
    'record_kind': 'PRIVATE_CANDIDATE_PREPARATION_RECEIPT', 'implementation_revision': code['head'],
    'commitment_sha256': made['commitment_sha256'], 'private_package_sha256': made['private_package_sha256'],
    'private_root': str(PRIVATE), 'target_cases': 200, 'schedule_slots': 450,
    'history_files': 374, 'published_layouts_excluded': 200, 'published_overlap_count': 0,
    'actual_cli_return_codes': [0, 0, 2], 'typed_prepare_verify_ok': True,
    'overwrite_refused_and_preserved': True, 'collector_unchanged': True,
    'collector_completed_slots': 3, 'collector_native_episode_count': 5,
    'remaining_hybrid_slots': 3, 'budget_and_history_and_calibration_unchanged': True,
    'public_storage': 'COMMITMENT_ONLY; no private payload, seed or new layouts in repository',
    'independent_custody': 'NOT_ESTABLISHED', 'status': 'PREPARED_NOT_RATIFIED',
    'native_episodes_executed': 0, 'model_calls': 0, 'new_budget_reservations': 0,
    'tests': {'targeted_observed': 22, 'authoritative_offline': 143,
              'first_worktree_attempt': {'passed': 142, 'failed': 1, 'retained': True}},
    'qualification_sampling_authorized': False, 'ready_for_large_test': False,
    'n_ge_50': 'FROZEN', 'AC90': 'NOT_RUN', 'protocol_and_budget_ratification': 'NOT_DONE',
    'reachability': 'NOT_EVALUATED', 'unrecorded_exposure': 'UNKNOWN',
    'network_stability': 'NOT_ACCEPTED', 'B_grasp_root_cause': 'UNKNOWN',
    'actual_invoice_and_gpu_cost': 'UNKNOWN'})
print(json.dumps({'ok': True, 'history_files': 374, 'target_cases': 200,
                  'excluded_public_layouts': 200, 'cli_return_codes': [0, 0, 2],
                  'commitment_sha256': made['commitment_sha256'], 'native_episodes_executed': 0}))
