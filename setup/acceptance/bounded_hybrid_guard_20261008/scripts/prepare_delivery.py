"""Mirror only the new guard and docs; capture the unchanged collector identity."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

TASK = Path('/home/ros/.codex/worktrees/16d1/flexcell')
WS = Path('/home/ros/agentic_workcell_ws')
WIN = Path('/mnt/c/dev/flexcell')
LOG = Path('/home/ros/fc_sync_logs/bounded_hybrid_guard_20261008')
ACTIVE = Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
FILES = ['setup/135_bounded_hybrid_resume.py', 'setup/transferbench/bounded_hybrid_guard.py',
         'setup/transferbench/test_bounded_hybrid_guard.py', 'docs/BOUNDED_HYBRID_GUARD.md',
         'docs/BOUNDED_RUNNER.md', 'docs/PRE_BATCH_CHECKPOINT.md', 'README.md']
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q
import bounded_runner as engine

def write(path, value):
    with path.open('xb') as stream: stream.write(q.encoded(value))

git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
q.require(subprocess.check_output(git + ['status', '--porcelain']) == b'', 'unrelated Windows changes')
q.require(subprocess.check_output(git + ['branch', '--show-current']).decode().strip()
          == 'feat/transferbench-foundation-20261006', 'wrong branch')
write(LOG / 'git_before.json', {'head': subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip(),
      'origin_feature': subprocess.check_output(git + ['rev-parse', 'origin/feat/transferbench-foundation-20261006']).decode().strip(),
      'origin_main': subprocess.check_output(git + ['rev-parse', 'origin/main']).decode().strip()})
write(LOG / 'owned_files.json', FILES)
for rel in FILES:
    target = WIN / rel; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TASK / rel, target)
cmd = ['/mnt/c/Yinyue/node/node.exe',
       'C:/Users/安帅潮/AppData/Local/npm-cache/_npx/7e4347a8d51f6fca/node_modules/prettier/bin/prettier.cjs',
       '--write', *['C:/dev/flexcell/' + rel for rel in FILES if rel.endswith('.md')]]
result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (LOG / 'prettier_source_attempt01.log').open('xb') as stream: stream.write(result.stdout)
q.require(result.returncode == 0, 'Prettier failed; preserve log')
for rel in FILES:
    for repo in (WS, TASK):
        target = repo / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WIN / rel, target)
    q.require(q.sha(WS / rel) == q.sha(WIN / rel) == q.sha(TASK / rel), 'source mirror differs')
state = engine.status(ACTIVE, WS)
plan, _, _, _, _ = engine.read(ACTIVE, WS)
q.require(state['state'] == 'PAUSED' and state['completed_slots'] == 3
          and state['native_episode_count'] == 5, 'collector already changed')
history = q.history_snapshot(Path(plan['history_path']))
pins = {str(p.relative_to(ACTIVE)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
        for p in sorted(ACTIVE.rglob('*')) if p.is_file()}
old = {}
for rel in ['bounded_runner_20261007', 'local_fsm_20261008', 'qualification_private_20261008']:
    root = WS / 'setup/acceptance' / rel
    manifest = q.loads((root / 'SHA256SUMS.json').read_bytes())
    for name, pin in manifest.items():
        path = q.regular(root, name)
        q.require(q.sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'old evidence changed')
    old[rel] = {'files': len(manifest), 'seal_sha256': q.sha(root / 'SHA256SUMS.json')}
write(LOG / 'before.json', {'recorded_utc': datetime.now(timezone.utc).isoformat(),
      'collector_status': state, 'collector_tree_sha256': q.digest(pins),
      'collector_executor_sha256': plan['executor_sha256'], 'history_files': len(history['files']),
      'history_sha256': q.digest(history), 'budget_sha256': q.sha(Path(plan['budget_path'])),
      'calibration_sha256': q.sha(Path('/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json')),
      'old_evidence_seals': old, 'mirrored_sha256': {rel: q.sha(WS / rel) for rel in FILES}})
print(json.dumps({'ok': True, 'mirrored_files': len(FILES), 'collector_unchanged': True,
                  'history_files': len(history['files'])}))
