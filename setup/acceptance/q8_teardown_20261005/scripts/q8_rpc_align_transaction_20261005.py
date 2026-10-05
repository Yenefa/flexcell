"""Preflight every collision before mutation; restore tested bytes on failure."""
from pathlib import Path
import hashlib
import subprocess
import sys

repo = Path('/home/ros/agentic_workcell_ws')
win = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone')
expected = 'fdb9775aebc170167879b44262bc94b92a871225'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo)
assert git('branch', '--show-current').decode().strip() == 'feat/clef-fast-arm'
assert git('rev-parse', 'HEAD').decode().strip() == '4e08c8448478fb86a2d369d5d6991f2e3d44cfbd'
read_only = '--inspect' in sys.argv
if not read_only:
    assert subprocess.run(['pgrep', '-f', '/setup/94_scenario_runner.py'],
                          stdout=subprocess.DEVNULL).returncode == 1, 'Wait for the active batch'
subprocess.run(['git', 'fetch', str(win), 'feat/clef-fast-arm'], cwd=repo, check=True)
assert git('rev-parse', 'FETCH_HEAD').decode().strip() == expected
files = ['setup/flexcell_admin.py',
         'src/flexcell/flexcell_skills/flexcell_skills/pose_request_worker.py',
         'src/flexcell/flexcell_skills/test/test_admin_pose_rpc.py']
incoming = {rel: git('show', expected + ':' + rel) for rel in files}
for rel, data in incoming.items():
    backup = Path('/tmp/q8_align_fdb9775') / Path(rel).name
    assert backup.read_bytes() == data
    if (repo / rel).exists():
        current = (repo / rel).read_bytes()
        if rel == 'setup/flexcell_admin.py':
            assert current in (data, git('show', 'HEAD:' + rel))
        else:
            assert current == data
untracked = {p.decode() for p in git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p}
tree = {p.decode() for p in git('ls-tree', '-r', '--name-only', '-z', expected).split(b'\0') if p}
collisions = sorted((untracked & tree) - set(files))
originals = {}
for rel in collisions:
    assert rel.startswith('setup/acceptance/q8_teardown_20261005/')
    assert (repo / rel).resolve().is_relative_to(repo.resolve())
    data = (repo / rel).read_bytes()
    assert data == git('show', expected + ':' + rel), 'Evidence collision differs: ' + rel
    originals[rel] = data
if read_only:
    print('PREFLIGHT: tested source backups and', len(collisions), 'evidence collisions byte-identical')
    sys.exit(0)
backup_root = Path('/tmp/q8_align_fdb9775_retry1')
for rel, data in {**originals, **incoming}.items():
    target = backup_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
try:
    subprocess.run(['git', 'restore', '--source=HEAD', '--', 'setup/flexcell_admin.py'], cwd=repo, check=True)
    for rel in files[1:]:
        (repo / rel).unlink(missing_ok=True)
    for rel in collisions:
        (repo / rel).unlink()
    subprocess.run(['git', 'merge', '--ff-only', '--no-stat', expected], cwd=repo, check=True)
except BaseException:
    for rel, data in {**originals, **incoming}.items():
        (repo / rel).write_bytes(data)
    raise
assert git('rev-parse', 'HEAD').decode().strip() == expected
for rel, data in {**originals, **incoming}.items():
    assert (repo / rel).read_bytes() == data
print('ALIGNED', expected, 'identical evidence collisions preserved:', len(collisions))
for rel in files:
    print(rel, hashlib.sha256((repo / rel).read_bytes()).hexdigest())
