"""Mirror owned files, format docs, and pin the unchanged live collector."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

TASK = Path('/home/ros/.codex/worktrees/16d1/flexcell')
WS = Path('/home/ros/agentic_workcell_ws')
WIN = Path('/mnt/c/dev/flexcell')
LOG = Path('/home/ros/fc_sync_logs/qualification_private_development_20261008')
ACTIVE = Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
FILES = ['setup/134_qualification_private.py', 'setup/transferbench/qualification_private.py',
         'setup/transferbench/test_qualification_private.py', 'docs/PRIVATE_QUALIFICATION_INPUTS.md',
         'docs/QUALIFICATION_PREPARATION.md', 'docs/PRE_BATCH_CHECKPOINT.md']
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q
import bounded_runner as engine

def write(path, data):
    with path.open('xb') as stream:
        stream.write(q.encoded(data))

write(LOG / 'owned_files.json', FILES)
git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
before = subprocess.check_output(git + ['status', '--porcelain']).decode()
q.require(before == '', 'Windows checkout changed before owned-file mirroring')
q.require(subprocess.check_output(git + ['branch', '--show-current']).decode().strip()
          == 'feat/transferbench-foundation-20261006', 'wrong delivery branch')
write(LOG / 'git_before.json', {'head': subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip(),
      'main': subprocess.check_output(git + ['rev-parse', 'origin/main']).decode().strip(), 'porcelain': before})
for rel in FILES:
    target = WIN / rel; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TASK / rel, target)
cmd = ['/mnt/c/Yinyue/node/node.exe',
       'C:/Users/安帅潮/AppData/Local/npm-cache/_npx/7e4347a8d51f6fca/node_modules/prettier/bin/prettier.cjs',
       '--write', *['C:/dev/flexcell/' + rel for rel in FILES if rel.startswith('docs/')]]
result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (LOG / 'prettier_source_attempt01.log').open('xb') as stream: stream.write(result.stdout)
q.require(result.returncode == 0, 'Prettier failed; preserve log')
for rel in FILES:
    for repo in (WS, TASK):
        target = repo / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WIN / rel, target)
    q.require(q.sha(WIN / rel) == q.sha(WS / rel) == q.sha(TASK / rel), 'mirror differs')
state = engine.status(ACTIVE, WS)
q.require(state['state'] == 'PAUSED' and state['completed_slots'] == 3 and
          state['native_episode_count'] == 5, 'unexpected collector state')
plan, rows, _, committed, ids = engine.read(ACTIVE, WS)
history = q.history_snapshot(Path(plan['history_path']))
def pins(root):
    return {str(p.relative_to(root)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
            for p in sorted(root.rglob('*')) if p.is_file()}
seals = {}
for rel in ('setup/acceptance/bounded_runner_20261007', 'setup/acceptance/local_fsm_20261008'):
    root = WS / rel
    manifest = q.loads((root / 'SHA256SUMS.json').read_bytes())
    for name, pin in manifest.items():
        path = q.regular(root, name)
        q.require(pin['sha256'] == q.sha(path) and pin['bytes'] == path.stat().st_size,
                  'old sealed evidence changed')
    seals[rel] = {'seal_sha256': q.sha(root / 'SHA256SUMS.json'), 'files': len(manifest)}
write(LOG / 'before.json', {'recorded_utc': datetime.now(timezone.utc).isoformat(),
      'collector_status': state, 'collector_tree_sha256': q.digest(pins(ACTIVE)),
      'collector_source_sha256': plan['source_sha256'],
      'history_sha256': q.digest(history), 'history_files': len(history['files']),
      'budget_sha256': q.sha(Path(plan['budget_path'])),
      'calibration_sha256': q.sha(Path('/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json')),
      'old_evidence_seals': seals, 'mirrored_files': {rel: q.sha(WS / rel) for rel in FILES}})
print(json.dumps({'ok': True, 'mirrored': len(FILES), 'history_files': len(history['files']),
                  'collector_state': state['state'], 'completed_slots': state['completed_slots']}))
