"""Seal the new guard's read-only receipt; preserve all prior sealed evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

WS = Path('/home/ros/agentic_workcell_ws')
TASK = Path('/home/ros/.codex/worktrees/16d1/flexcell')
WIN = Path('/mnt/c/dev/flexcell')
LOG = Path('/home/ros/fc_sync_logs/bounded_hybrid_guard_20261008')
ROOT = WS / 'setup/acceptance/bounded_hybrid_guard_20261008'
sys.path.insert(0, str(WS / 'setup/transferbench'))
import qualification_prepare as q
import bounded_runner as runner

q.require(not (ROOT / 'SHA256SUMS.json').exists(), 'receipt already sealed; do not amend')
code = q.loads((LOG / 'code_commit.json').read_bytes())
git = ['/mnt/c/Program Files/Git/cmd/git.exe', '-C', 'C:/dev/flexcell']
for rel in code['files']:
    raw = subprocess.check_output(git + ['show', code['head'] + ':' + rel])
    q.require(raw == (WS / rel).read_bytes(), 'executed source differs from implementation commit')
    target = ROOT / 'source' / rel; target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream: stream.write(raw)
for name in ['owned_files.json', 'git_before.json', 'code_commit.json', 'before.json',
             'tests_targeted_attempt01.log', 'tests_all_authority_attempt01.log',
             'prettier_source_attempt01.log', 'commit_source_attempt01.log']:
    target = ROOT / 'validation' / name
    q.require(not target.exists(), 'validation copy exists')
    shutil.copy2(LOG / name, target)
for name in ['prepare_delivery.py', 'commit_source.py', 'register_readonly.py', 'seal_public.py']:
    target = ROOT / 'scripts' / name; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOG / name, target)

# Record the experiment in its existing index without touching frozen tools.
exp = TASK / 'docs/EXPERIMENTS.md'
body = exp.read_text()
q.require('### TB-RUN-003' not in body, 'experiment already recorded')
entry = '''### TB-RUN-003 — Guarded Hybrid continuation prepared (2026-10-08)

- **Change**: an independently pinned `135_bounded_hybrid_resume.py` adapter
  checks raw fast proposals and positive measured tokens before committing each
  remaining Hybrid logical task. Zero-fast green results halt the original
  collector; original native failures and all evidence remain intact.
- **Validation**: 31 targeted and 174 authoritative offline instrument tests
  passed. Actual register/status/default-run returned rc=0; overwrite refused
  with rc=2. The current 3-task / 5-episode FSM prefix, 374-file history, budget,
  calibration and old seals are unchanged; private inputs still verify.
- **Boundary**: home GPU remains offline; actual guarded Hybrid execution,
  qualification and AC@90 are NOT_RUN, n≥50 stays FROZEN. The guard is a new
  development instrument and cannot be pooled with unguarded attempts. No new
  native episodes, model calls or budget reservations occurred.
- **Evidence**: [sealed preparation receipt](../setup/acceptance/bounded_hybrid_guard_20261008/README.md),
  [operator entry](BOUNDED_HYBRID_GUARD.md).

'''
q.require('\n## Evidence locations\n' in body, 'experiment insertion marker missing')
exp.write_text(body.replace('\n## Evidence locations\n', '\n' + entry + '## Evidence locations\n', 1))
for rel, source in [('setup/acceptance/bounded_hybrid_guard_20261008/README.md', ROOT / 'README.md'),
                    ('docs/EXPERIMENTS.md', exp)]:
    target = WIN / rel; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
cmd = ['/mnt/c/Yinyue/node/node.exe',
       'C:/Users/安帅潮/AppData/Local/npm-cache/_npx/7e4347a8d51f6fca/node_modules/prettier/bin/prettier.cjs',
       '--write', 'C:/dev/flexcell/setup/acceptance/bounded_hybrid_guard_20261008/README.md',
       'C:/dev/flexcell/docs/EXPERIMENTS.md']
formatted = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (ROOT / 'validation/prettier_evidence_attempt01.log').open('xb') as stream: stream.write(formatted.stdout)
q.require(formatted.returncode == 0, 'Prettier failed; keep log')
shutil.copy2(WIN / 'setup/acceptance/bounded_hybrid_guard_20261008/README.md', ROOT / 'README.md')
for repo in (WS, TASK): shutil.copy2(WIN / 'docs/EXPERIMENTS.md', repo / 'docs/EXPERIMENTS.md')
private = Path('/home/ros/fc_sync_logs/qualification_private_20261008/inputs')
seed = str(q.loads((private / 'protocol.json').read_bytes())['seed']).encode()
public_paths = [p for p in ROOT.rglob('*') if p.is_file()] + [WS / rel for rel in code['files']] + [exp]
q.require(all(seed not in p.read_bytes() for p in public_paths), 'private seed leaked')
runner.write(ROOT / 'validation/disclosure_check.json', {
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'private_seed_not_published': True,
    'private_package_not_copied': True, 'checked_public_files': len(public_paths)})
manifest = {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': q.sha(p)}
            for p in sorted(ROOT.rglob('*')) if p.is_file()}
runner.write(ROOT / 'SHA256SUMS.json', manifest)
for rel, pin in manifest.items():
    path = q.regular(ROOT, rel)
    q.require(q.sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'receipt seal mismatch')
for repo in (WIN, TASK):
    for path in ROOT.rglob('*'):
        if path.is_file():
            target = repo / path.relative_to(WS); target.parent.mkdir(parents=True, exist_ok=True)
            q.require(not target.exists() or target.read_bytes() == path.read_bytes(), 'unrelated target differs')
            shutil.copy2(path, target)
    for path in ROOT.rglob('*'):
        if path.is_file(): q.require(q.sha(repo / path.relative_to(WS)) == q.sha(path), 'mirror differs')
result = {'ok': True, 'receipt_files': len(manifest), 'seal_sha256': q.sha(ROOT / 'SHA256SUMS.json'),
          'three_trees_identical': True, 'private_package_committed': False}
runner.write(LOG / 'seal_result.json', result)
print(json.dumps(result))
