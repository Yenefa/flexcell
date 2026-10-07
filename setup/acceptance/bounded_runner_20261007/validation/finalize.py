"""Seal the actual pre-dispatch stop; never dispatch, overwrite, or turn it green."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
ROOT = WS / 'setup/acceptance/bounded_runner_20261007'
LOG = Path('/home/ros/fc_sync_logs/bounded_runner_20261007')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import bounded_runner as runner
import qualification_prepare as q

state = runner.status(ROOT / 'run', WS)
plan = q.loads((ROOT / 'run/plan.json').read_bytes())
rows = [q.loads(line) for line in (ROOT / 'run/events.jsonl').read_bytes().splitlines()]
q.require(state['state'] == 'STOPPED' and state['completed_slots'] == 0
          and state['native_dispatch_quota_used'] == 0
          and [row['event'] for row in rows] == ['REGISTERED', 'STOPPED'],
          'only the actual zero-claim stop may be sealed by this script')
history = q.history_snapshot(Path(plan['history_path']))
q.require(q.same_typed(history['files'], plan['history_files']), 'episode history changed')
q.require(q.sha(Path(plan['budget_path'])) == plan['registration_budget']['source_sha256'],
          'persistent budget changed')
local = q.loads((ROOT / 'validation/local_readonly_attempt01.json').read_bytes())
q.require(type(local['local_health']['return_code']) is int
          and local['local_health']['return_code'] == 0, 'local health process unconfirmed')
health = q.loads(local['local_health']['stdout'])
q.require(health['ok'] is True and health['busy'] is False and health['hard_fail'] == []
          and health['checks']['task_state'] == 'IDLE'
          and health['checks']['carry_engaged'] is False, 'local state not confirmed released')
q.require(local['network']['self_online'] is True
          and len(local['network']['peer']) == 1
          and local['network']['peer'][0]['Online'] is False,
          'this report requires the recorded offline peer snapshot')
for name in ['code_commit.json', 'tests_attempt01.log', 'tests_all_attempt01.log',
             'dry_run_attempt01.json', 'network_readonly_attempt01.json',
             'prettier_source_attempt01.log', 'prettier_evidence_attempt01.log',
             'run_prefix.sh', 'local_readonly.sh']:
    target = ROOT / 'validation' / name
    q.require(not target.exists(), 'refuse to replace validation: ' + name)
    shutil.copy2(LOG / name, target)
q.require('29 passed' in (ROOT / 'validation/tests_attempt01.log').read_text()
          and '111 passed' in (ROOT / 'validation/tests_all_attempt01.log').read_text(),
          'actual targeted test logs required')
code = q.loads((ROOT / 'validation/code_commit.json').read_bytes())
git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
remote_output = subprocess.check_output(git + ['ls-remote', 'origin',
    'refs/heads/feat/transferbench-foundation-20261006', 'refs/heads/main'], text=True)
remote = {line.split()[1]: line.split()[0] for line in remote_output.splitlines()}
q.require(remote['refs/heads/feat/transferbench-foundation-20261006'] == code['head'],
          'implementation push is not confirmed')
runner.write(ROOT / 'validation/code_delivery.json', {
    'verified_utc': datetime.now(timezone.utc).isoformat(), 'implementation_revision': code['head'],
    'remote_refs': remote, 'source_push_confirmed': True, 'main_merged': False})
for rel in code['files']:
    target = ROOT / 'source' / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    q.require(not target.exists(), 'source snapshot already exists')
    committed = subprocess.check_output(git + ['show', code['head'] + ':' + rel])
    if not rel.startswith('docs/'):
        q.require((WS / rel).read_bytes() == committed, 'executed code differs from commit: ' + rel)
    with target.open('xb') as stream:
        stream.write(committed)
report = dict(record_kind='BOUNDED_RUNNER_DEVELOPMENT_RECEIPT',
    implementation='DELIVERED', implementation_revision=code['head'],
    execution='PRE_DISPATCH_BLOCKED', execution_complete=False,
    runner_status=state, history_files=len(history['files']), history_unchanged=True,
    persistent_budget_unchanged=True, native_episodes=0, inference_calls=0,
    retained_preflight_failures=1, driver_return_code=1, execute_return_code=2,
    native_dispatch_quota_used=0, planned_native_episode_limit=10,
    live_pause_resume='NOT_RUN', actual_task_outcomes='NOT_RUN', decision_latency_ms='NOT_RUN',
    local_strict_health_ok=True, endpoint_peer_online=False,
    endpoint='100.87.190.44', offline_root_cause='UNKNOWN',
    literal_endpoint_proxy_bypass=local['literal_endpoint_proxy_bypass'],
    ros_domain_id=local['ros_domain_id'], rmw_implementation=local['rmw_implementation'],
    tests={'new_runner': 29, 'all_offline_instruments': 111},
    no_failure_replacement=True, qualification_sampling_authorized=False,
    ready_for_large_test=False, n_ge_50='FROZEN', AC90='NOT_RUN',
    network_stability='NOT_ACCEPTED', B_grasp_root_cause='UNKNOWN',
    gpu_and_actual_api_fees='UNKNOWN')
runner.write(ROOT / 'report.json', report)
manifest = {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
            for p in sorted(ROOT.rglob('*')) if p.is_file()
            and str(p.relative_to(ROOT)) != 'SHA256SUMS.json'}
runner.write(ROOT / 'SHA256SUMS.json', manifest)
for rel, pin in manifest.items():
    p = q.regular(ROOT, rel)
    q.require(q.sha(p) == pin['sha256'] and p.stat().st_size == pin['bytes'], 'seal mismatch')
print(json.dumps({'sealed_files': len(manifest), 'execution': report['execution'],
    'source_push_confirmed': True, 'native_episodes': 0,
    'ready_for_large_test': False, 'n_ge_50': 'FROZEN'}))
