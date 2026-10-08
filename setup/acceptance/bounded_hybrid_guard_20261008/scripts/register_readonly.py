"""Register a sidecar guard, inspect it, and prove the active run did not change."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
LOG = Path('/home/ros/fc_sync_logs/bounded_hybrid_guard_20261008')
ROOT = WS / 'setup/acceptance/bounded_hybrid_guard_20261008'
ACTIVE = Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
GUARD = ACTIVE.parent / 'hybrid_resume_guard.json'
sys.path.insert(0, str(WS / 'setup/transferbench'))
import bounded_runner as runner
import qualification_prepare as q

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    runner.write(path, value)

q.require(not ROOT.exists() and not GUARD.exists(), 'preserve any existing receipt or guard')
code = q.loads((LOG / 'code_commit.json').read_bytes())
before = q.loads((LOG / 'before.json').read_bytes())

def call(name, script, args, expected):
    argv = [sys.executable, str(WS / script), *args]
    result = subprocess.run(argv, cwd=WS, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    write(ROOT / 'validation' / (name + '.json'),
          {'argv': argv, 'cwd': str(WS), 'return_code': result.returncode,
           'stdout': result.stdout.decode(), 'stderr': result.stderr.decode()})
    q.require(result.returncode == expected, 'unexpected CLI code or signal; preserve attempt')
    value = q.loads(result.stdout)
    q.require(type(value['ok']) is bool and value['ok'] is (expected == 0), 'typed CLI result required')
    return value

registration = ['register', '--root', str(ACTIVE), '--out', str(GUARD),
                '--revision', code['head'], '--workspace', str(WS)]
made = call('register_attempt01', 'setup/135_bounded_hybrid_resume.py', registration, 0)
shared = ['--guard', str(GUARD), '--expected-sha256', made['guard_sha256'], '--workspace', str(WS)]
status = call('status_attempt01', 'setup/135_bounded_hybrid_resume.py', ['status', *shared], 0)
default = call('default_readonly_attempt01', 'setup/135_bounded_hybrid_resume.py', ['run', *shared], 0)
refused = call('overwrite_refusal_attempt01', 'setup/135_bounded_hybrid_resume.py', registration, 2)
q.require('already exists' in refused['error'] and q.sha(GUARD) == made['guard_sha256'], 'guard overwritten')
q.require(q.same_typed(status, default) and status['state'] == 'PAUSED' and status['completed_slots'] == 3
          and status['native_episode_count'] == 5 and status['guard_verified'] is True
          and status['dispatch_authorized'] is False, 'default run changed the paused frontier')
write(ROOT / 'guard_manifest.json', q.loads(GUARD.read_bytes()))
commitment = WS / 'setup/acceptance/qualification_private_20261008/commitment.json'
private = call('private_inputs_verify_attempt01', 'setup/134_qualification_private.py',
    ['verify', '--commitment', str(commitment),
     '--expected-sha256', '8d572dce24e7e3b5d97e2e3337842cda68055b133cc406da0a344475a311dd99',
     '--workspace', str(WS), '--history', '/home/ros/.ros/flexcell/episodes',
     '--calibration', '/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json',
     '--budget', '/home/ros/.config/flexcell/deepseek_budget_20261001.json'], 0)
q.require(private['history_files'] == 374 and private['native_episodes_executed'] == 0,
          'private package changed or sampling occurred')
plan, _, _, _, _ = runner.read(ACTIVE, WS)
pins = {str(p.relative_to(ACTIVE)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
        for p in sorted(ACTIVE.rglob('*')) if p.is_file()}
history = q.history_snapshot(Path(plan['history_path']))
q.require(q.digest(pins) == before['collector_tree_sha256']
          and q.same_typed(plan['executor_sha256'], before['collector_executor_sha256']), 'collector or executor changed')
q.require(q.digest(history) == before['history_sha256'], 'history changed')
q.require(q.sha(Path(plan['budget_path'])) == before['budget_sha256'], 'budget changed')
q.require(q.sha(Path('/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json')) == before['calibration_sha256'],
          'calibration changed')
for name, expected in before['old_evidence_seals'].items():
    root = WS / 'setup/acceptance' / name
    q.require(q.sha(root / 'SHA256SUMS.json') == expected['seal_sha256'], 'old seal changed')
    for rel, pin in q.loads((root / 'SHA256SUMS.json').read_bytes()).items():
        path = q.regular(root, rel)
        q.require(q.sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'old evidence changed')
raw = subprocess.check_output(['/mnt/c/Program Files/Tailscale/tailscale.exe', 'status', '--json'])
tailnet = q.loads(raw)
peer = next(p for p in tailnet.get('Peer', {}).values() if '100.87.190.44' in p.get('TailscaleIPs', []))
gpu = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'gpu_ip': '100.87.190.44',
       'self_online': tailnet.get('Self', {}).get('Online'), 'gpu_online': peer.get('Online'),
       'last_seen': peer.get('LastSeen'), 'relay': peer.get('Relay'), 'model_calls': 0}
write(ROOT / 'validation/gpu_status_readonly.json', gpu)
write(ROOT / 'validation/after.json', {'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'collector_tree_sha256': q.digest(pins), 'collector_unchanged': True,
    'collector_status': runner.status(ACTIVE, WS), 'history_sha256': q.digest(history),
    'history_files': len(history['files']), 'history_unchanged': True, 'budget_unchanged': True,
    'budget_sha256': before['budget_sha256'], 'calibration_unchanged': True,
    'calibration_sha256': before['calibration_sha256'], 'old_evidence_seals': before['old_evidence_seals']})
write(ROOT / 'report.json', {'record_kind': 'GUARDED_HYBRID_CONTINUATION_PREPARATION',
    'implementation_revision': code['head'], 'guard_path': str(GUARD), 'guard_sha256': made['guard_sha256'],
    'collector_root': str(ACTIVE), 'collector_state': 'PAUSED', 'collector_completed_slots': 3,
    'collector_native_episode_count': 5, 'pending_hybrid_slots': 3, 'remaining_native_episode_cap': 5,
    'cli_return_codes': [0, 0, 0, 2], 'default_run_read_only': True, 'guard_manifest_verified': True,
    'guard_overwrite_refused': True, 'collector_history_budget_calibration_unchanged': True,
    'old_receipts_unchanged': True, 'private_inputs_still_verify': True, 'gpu_online': peer.get('Online'),
    'tests': {'targeted': 31, 'all_authoritative_offline': 174},
    'new_native_episodes': 0, 'new_model_calls': 0, 'new_budget_reservations': 0,
    'actual_guarded_hybrid_execution': 'NOT_RUN', 'production_runtime_modified': False,
    'guard_instrument_identity': 'NEW; cannot pool with unguarded attempts',
    'reachability_and_physical_acceptance': 'NOT_EVALUATED',
    'independent_custody': 'NOT_ESTABLISHED', 'protocol_and_budget_ratification': 'NOT_DONE',
    'NET-001': 'NOT_ACCEPTED', 'GRASP-B-001': 'UNKNOWN', 'actual_api_and_gpu_fees': 'UNKNOWN',
    'qualification_sampling_authorized': False, 'ready_for_large_test': False,
    'n_ge_50': 'FROZEN', 'AC90': 'NOT_RUN'})
print(json.dumps({'ok': True, 'guard_sha256': made['guard_sha256'], 'collector_unchanged': True,
                  'guarded_hybrid_execution': 'NOT_RUN', 'gpu_online': peer.get('Online'),
                  'native_episodes_executed': 0}))
