"""Commit only the mirrored offline implementation, before generating inputs."""
import json
from pathlib import Path
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
LOG = Path('/home/ros/fc_sync_logs/qualification_private_development_20261008')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q

files = q.loads((LOG / 'owned_files.json').read_bytes())
q.require('143 passed' in (LOG / 'tests_all_authority_attempt02.log').read_text(), 'offline checks incomplete')
git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
before = q.loads((LOG / 'git_before.json').read_bytes())
q.require(subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip() == before['head'], 'branch moved')
q.require(subprocess.check_output(git + ['diff', '--cached', '--name-only']) == b'', 'unrelated staged changes')
status = subprocess.check_output(git + ['status', '--porcelain']).decode()
q.require({line[3:] for line in status.splitlines()} == set(files), 'unexpected Windows changed files')
subprocess.run(git + ['diff', '--check'], check=True)
subprocess.run(git + ['add', '--', *files], check=True)
q.require(set(subprocess.check_output(git + ['diff', '--cached', '--name-only']).decode().splitlines()) == set(files),
          'index differs from owned files')
result = subprocess.run(git + ['commit', '-m', 'feat(benchmark): stage private candidates with public exposure exclusions'],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (LOG / 'commit_source_attempt01.log').open('xb') as stream: stream.write(result.stdout)
q.require(result.returncode == 0, 'source commit failed')
head = subprocess.check_output(git + ['rev-parse', 'HEAD']).decode().strip()
for rel in files:
    q.require(subprocess.check_output(git + ['show', head + ':' + rel]) == (WS / rel).read_bytes(),
              'authoritative execution source differs from commit')
with (LOG / 'code_commit.json').open('xb') as stream:
    stream.write(q.encoded({'head': head, 'parent': before['head'], 'files': files, 'offline_tests': 143,
                           'private_inputs_committed': False, 'native_episodes_executed': 0}))
print(json.dumps({'ok': True, 'head': head, 'offline_tests': 143}))
