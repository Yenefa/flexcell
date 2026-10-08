"""Seal public evidence only; never copy the private package into any Git tree."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
TASK = Path('/home/ros/.codex/worktrees/16d1/flexcell')
WIN = Path('/mnt/c/dev/flexcell')
LOG = Path('/home/ros/fc_sync_logs/qualification_private_development_20261008')
ROOT = WS / 'setup/acceptance/qualification_private_20261008'
PRIVATE = Path('/home/ros/fc_sync_logs/qualification_private_20261008/inputs')
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q

q.require(not (ROOT / 'SHA256SUMS.json').exists(), 'public receipt already sealed')
code = q.loads((LOG / 'code_commit.json').read_bytes())
git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
for rel in code['files']:
    raw = subprocess.check_output(git + ['show', code['head'] + ':' + rel])
    q.require((WS / rel).read_bytes() == raw, 'executed source differs from implementation commit')
    target = ROOT / 'source' / rel; target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream: stream.write(raw)
for name in ['owned_files.json', 'git_before.json', 'code_commit.json', 'before.json',
             'retained_failures.json', 'tests_all_attempt01.log', 'tests_all_authority_attempt02.log',
             'prettier_source_attempt01.log', 'commit_source_attempt01.log']:
    target = ROOT / 'validation' / name
    q.require(not target.exists(), 'evidence copy exists')
    shutil.copy2(LOG / name, target)
for name in ['prepare_delivery.py', 'capture_before.py', 'commit_source.py', 'run_private.py', 'seal_public.py']:
    target = ROOT / 'scripts' / name; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOG / name, target)

# Format the evidence document before calculating its seal.
target = WIN / ROOT.relative_to(WS) / 'README.md'
target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / 'README.md', target)
cmd = ['/mnt/c/Yinyue/node/node.exe',
       'C:/Users/安帅潮/AppData/Local/npm-cache/_npx/7e4347a8d51f6fca/node_modules/prettier/bin/prettier.cjs',
       '--write', 'C:/dev/flexcell/' + str(ROOT.relative_to(WS) / 'README.md')]
result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (ROOT / 'validation/prettier_evidence_attempt01.log').open('xb') as stream: stream.write(result.stdout)
q.require(result.returncode == 0, 'evidence formatting failed; preserve attempt')
shutil.copy2(target, ROOT / 'README.md')

# Check actual secret material in memory, printing/storing only the verdict.
secret = str(q.loads((PRIVATE / 'protocol.json').read_bytes())['seed']).encode()
public_paths = [p for p in ROOT.rglob('*') if p.is_file()] + [WS / rel for rel in code['files']]
q.require(all(secret not in p.read_bytes() for p in public_paths), 'private seed leaked into public artifacts')
def no_private_geometry(value):
    if type(value) is dict:
        q.require(not set(value) & {'initial_objects', 'position'}, 'new geometry in public receipt')
        for child in value.values(): no_private_geometry(child)
    elif type(value) is list:
        for child in value: no_private_geometry(child)
for p in ROOT.rglob('*.json'):
    no_private_geometry(q.loads(p.read_bytes()))
value = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
         'private_seed_not_present_in_public_artifacts': True,
         'private_geometry_not_present_in_public_receipt_json': True,
         'private_payload_not_copied': True,
         'checked_public_files': len(public_paths), 'model_calls': 0, 'native_episodes_executed': 0}
with (ROOT / 'validation/disclosure_check.json').open('xb') as stream: stream.write(q.encoded(value))
manifest = {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
            for p in sorted(ROOT.rglob('*')) if p.is_file()}
with (ROOT / 'SHA256SUMS.json').open('xb') as stream: stream.write(q.encoded(manifest))
for rel, pin in manifest.items():
    path = q.regular(ROOT, rel)
    q.require(q.sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'public seal mismatch')
for repo in (WIN, TASK):
    for p in ROOT.rglob('*'):
        if p.is_file():
            target = repo / p.relative_to(WS); target.parent.mkdir(parents=True, exist_ok=True)
            q.require(not target.exists() or target.read_bytes() == p.read_bytes(), 'unrelated target exists')
            shutil.copy2(p, target)
    for p in ROOT.rglob('*'):
        if p.is_file(): q.require(q.sha(repo / p.relative_to(WS)) == q.sha(p), 'public mirror differs')
record = {'ok': True, 'public_receipt_files': len(manifest), 'seal_sha256': q.sha(ROOT / 'SHA256SUMS.json'),
          'private_package_committed': False, 'all_three_trees_identical': True}
with (LOG / 'seal_result.json').open('xb') as stream: stream.write(q.encoded(record))
print(json.dumps(record))
