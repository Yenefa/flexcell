#!/usr/bin/env python3
"""Back up and update only the skills source and its matching runtime modules."""
import hashlib
import json
from pathlib import Path
import shutil


def main():
    task = Path('/home/ros/.codex/worktrees/16d1/flexcell')
    ws = Path('/home/ros/agentic_workcell_ws')
    win = Path('/mnt/c/dev/flexcell')
    logs = Path('/home/ros/fc_sync_logs/route_hardening_20261006')
    files = [
        'src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py',
        'src/flexcell/flexcell_skills/flexcell_skills/observe_server.py',
        'src/flexcell/flexcell_skills/flexcell_skills/contracts/episode.py',
        'src/flexcell/flexcell_skills/flexcell_skills/contracts/goal_response.py',
        'src/flexcell/flexcell_skills/package.xml',
        'src/flexcell/flexcell_skills/test/test_executor_integration.py',
        'src/flexcell/flexcell_skills/test/test_goal_response.py',
        'setup/122_sendgoal_probe.py',
    ]
    assert not (logs / 'transport_sync.json').exists(), 'Do not overwrite deployment evidence'
    for rel in files:
        old, reference = ws / rel, win / rel
        assert old.exists() == reference.exists(), rel
        if old.exists():
            assert old.read_bytes() == reference.read_bytes(), 'Concurrent source change: ' + rel
    receipt = []
    for rel in files:
        source, target = task / rel, ws / rel
        if target.exists():
            backup = logs / 'backup/source' / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        receipt.append(dict(path=rel, sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    package = 'src/flexcell/flexcell_skills/flexcell_skills/'
    installed = Path('/home/ros/.local/share/flexcell/mainline/install/flexcell_skills/lib/python3.12/site-packages/flexcell_skills')
    for rel in files:
        if not rel.startswith(package):
            continue
        target = installed / rel[len(package):]
        if target.exists():
            backup = logs / 'backup/installed' / rel[len(package):]
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(task / rel, target)
        assert target.read_bytes() == (task / rel).read_bytes()
    (logs / 'transport_sync.json').write_text(json.dumps(dict(files=receipt,
        scope='Only flexcell_skills modules; install/build layout preserved'), indent=2) + '\n')
    print('Updated source and runtime skills modules with backups.')


if __name__ == '__main__':
    main()
