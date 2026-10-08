"""Complete read-only baseline capture after the retained producer KeyError."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

WS = Path('/home/ros/agentic_workcell_ws')
LOG = Path('/home/ros/fc_sync_logs/qualification_private_development_20261008')
ACTIVE = Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q
import bounded_runner as engine

files = q.loads((LOG / 'owned_files.json').read_bytes())
for rel in files:
    q.require(q.sha(WS / rel) == q.sha(Path('/mnt/c/dev/flexcell') / rel) ==
              q.sha(Path('/home/ros/.codex/worktrees/16d1/flexcell') / rel), 'mirror differs')
state = engine.status(ACTIVE, WS)
q.require(state['state'] == 'PAUSED' and state['completed_slots'] == 3 and
          state['native_episode_count'] == 5, 'unexpected collector state')
plan, _, _, _, _ = engine.read(ACTIVE, WS)
history = q.history_snapshot(Path(plan['history_path']))
active_pins = {str(p.relative_to(ACTIVE)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
               for p in sorted(ACTIVE.rglob('*')) if p.is_file()}
seals = {}
for rel in ('setup/acceptance/bounded_runner_20261007', 'setup/acceptance/local_fsm_20261008'):
    root = WS / rel
    manifest = q.loads((root / 'SHA256SUMS.json').read_bytes())
    for name, pin in manifest.items():
        path = q.regular(root, name)
        q.require(pin['sha256'] == q.sha(path) and pin['bytes'] == path.stat().st_size,
                  'old sealed evidence changed')
    seals[rel] = {'seal_sha256': q.sha(root / 'SHA256SUMS.json'), 'files': len(manifest)}
value = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
         'collector_status': state, 'collector_tree_sha256': q.digest(active_pins),
         'collector_source_sha256': plan['executor_sha256'],
         'history_sha256': q.digest(history), 'history_files': len(history['files']),
         'budget_sha256': q.sha(Path(plan['budget_path'])),
         'calibration_sha256': q.sha(Path('/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json')),
         'old_evidence_seals': seals, 'mirrored_files': {rel: q.sha(WS / rel) for rel in files}}
with (LOG / 'before.json').open('xb') as stream: stream.write(q.encoded(value))
with (LOG / 'retained_failures.json').open('xb') as stream:
    stream.write(q.encoded([
        {'command': 'python3 -m pytest -q setup/transferbench',
         'cwd': '/home/ros/.codex/worktrees/16d1/flexcell', 'return_code': 1,
         'log': 'tests_all_attempt01.log', 'passed': 142, 'failed': 1,
         'cause': 'historical ledger pin includes authoritative absolute receipt path; task worktree path differs',
         'resolution': 'run unchanged tests and unchanged historical receipts in authoritative workspace'},
        {'command': 'python3 prepare_delivery.py', 'return_code': 1,
         'error': "KeyError: 'source_sha256'", 'artifact': 'prepare_delivery.py',
         'cause': 'producer used wrong plan key; correct registered key is executor_sha256',
         'resolution': 'capture_before.py only; original producer and collector preserved'}]))
print(json.dumps({'ok': True, 'history_files': len(history['files']), 'state': state['state'],
                  'completed_slots': state['completed_slots']}))
