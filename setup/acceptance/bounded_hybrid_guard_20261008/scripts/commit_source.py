"""Commit the new instrument before registering its actual fixed identity."""
import json
from pathlib import Path
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
LOG = Path('/home/ros/fc_sync_logs/bounded_hybrid_guard_20261008')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q

files = q.loads((LOG / 'owned_files.json').read_bytes())
q.require('174 passed' in (LOG / 'tests_all_authority_attempt01.log').read_text(), 'offline checks incomplete')
git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
before = q.loads((LOG / 'git_before.json').read_bytes())
q.require(subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip() == before['head'], 'branch moved')
q.require(subprocess.check_output(git + ['diff', '--cached', '--name-only']) == b'', 'unrelated index changes')
changed = subprocess.check_output(git + ['status', '--porcelain']).decode()
q.require({line[3:] for line in changed.splitlines()} == set(files), 'unexpected Windows changes')
subprocess.run(git + ['diff', '--check'], check=True)
subprocess.run(git + ['add', '--', *files], check=True)
q.require(set(subprocess.check_output(git + ['diff', '--cached', '--name-only']).decode().splitlines()) == set(files),
          'index differs from owned files')
result = subprocess.run(git + ['commit', '-m', 'feat(runtime): guard frozen Hybrid continuation against absent fast arm'],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (LOG / 'commit_source_attempt01.log').open('xb') as stream: stream.write(result.stdout)
q.require(result.returncode == 0, 'source commit failed; preserve log')
head = subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip()
for rel in files:
    q.require(subprocess.check_output(git + ['show', head + ':' + rel]) == (WS / rel).read_bytes(),
              'authoritative source differs from commit')
with (LOG / 'code_commit.json').open('xb') as stream:
    stream.write(q.encoded({'head': head, 'parent': before['head'], 'files': files,
        'targeted_tests': 31, 'offline_tests': 174, 'production_modified': False,
        'runtime_fingerprint_changed': False, 'new_guard_instrument_identity': True}))
print(json.dumps({'ok': True, 'head': head, 'offline_tests': 174}))
