"""Fast-forward docs/evidence only; preserve byte-identical incoming collisions."""
from pathlib import Path
import json
import subprocess
import sys

repo = Path('/home/ros/agentic_workcell_ws')
win = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone')
expected = sys.argv[1]
previous = 'fdb9775aebc170167879b44262bc94b92a871225'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo)

assert git('branch', '--show-current').decode().strip() == 'feat/clef-fast-arm'
assert git('rev-parse', 'HEAD').decode().strip() == previous
assert not git('diff', '--name-only').strip(), 'Tracked runtime files must be clean'
assert subprocess.run(['pgrep', '-f', '/setup/94_scenario_runner.py'],
                      stdout=subprocess.DEVNULL).returncode == 1, 'Wait for the active batch'
subprocess.run(['git', 'fetch', str(win), 'feat/clef-fast-arm'], cwd=repo, check=True)
assert git('rev-parse', 'FETCH_HEAD').decode().strip() == expected
changed = git('diff', '--name-only', previous, expected).decode().splitlines()
assert changed and all(p.startswith(('docs/', 'setup/acceptance/q8_teardown_20261005/')) for p in changed), changed
untracked = {p.decode() for p in git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p}
tree = {p.decode() for p in git('ls-tree', '-r', '--name-only', '-z', expected).split(b'\0') if p}
originals = {}
for rel in sorted(untracked & tree):
    assert rel.startswith('setup/acceptance/q8_teardown_20261005/')
    target = repo / rel
    assert target.resolve().is_relative_to(repo.resolve())
    data = target.read_bytes()
    assert data == git('show', expected + ':' + rel), 'Evidence collision differs: ' + rel
    originals[rel] = data
backup_root = Path('/tmp') / ('q8_final_align_' + expected[:12])
for rel, data in originals.items():
    backup = backup_root / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(data)
try:
    for rel in originals:
        (repo / rel).unlink()
    subprocess.run(['git', 'merge', '--ff-only', '--no-stat', expected], cwd=repo, check=True)
except BaseException:
    for rel, data in originals.items():
        (repo / rel).write_bytes(data)
    raise
assert git('rev-parse', 'HEAD').decode().strip() == expected
for rel, data in originals.items():
    assert (repo / rel).read_bytes() == data
print(json.dumps(dict(aligned=expected, changed_documents_or_evidence=len(changed),
                      collisions_preserved=len(originals), source_unchanged=True)))
