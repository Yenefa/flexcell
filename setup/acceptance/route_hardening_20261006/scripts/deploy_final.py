#!/usr/bin/env python3
"""Deploy the reviewed transport delta after freezing the first runtime."""
import hashlib
import json
from pathlib import Path
import shutil


def main():
    task = Path('/home/ros/.codex/worktrees/16d1/flexcell')
    workspace = Path('/home/ros/agentic_workcell_ws')
    logs = Path('/home/ros/fc_sync_logs/route_hardening_20261006')
    installed = Path('/home/ros/.local/share/flexcell/mainline/install/flexcell_skills/lib/python3.12/site-packages/flexcell_skills')
    receipt = logs / 'final_sync.json'
    assert not receipt.exists(), 'Preserve deployment receipt'
    phase1 = json.loads((logs / 'phase1/deployment.json').read_text())
    files = ['src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py',
             'src/flexcell/flexcell_skills/flexcell_skills/contracts/goal_response.py',
             'src/flexcell/flexcell_skills/test/test_executor_integration.py']
    copied = []
    for rel in files:
        if rel in phase1['source_sha256']:
            assert hashlib.sha256((workspace / rel).read_bytes()).hexdigest() == phase1['source_sha256'][rel]
        backup = logs / 'backup/final_source' / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / rel, backup)
        shutil.copy2(task / rel, workspace / rel)
        prefix = 'src/flexcell/flexcell_skills/flexcell_skills/'
        if rel.startswith(prefix):
            target = installed / rel[len(prefix):]
            shutil.copy2(task / rel, target)
            assert target.read_bytes() == (workspace / rel).read_bytes()
        copied.append(dict(path=rel, sha256=hashlib.sha256((workspace / rel).read_bytes()).hexdigest()))
    receipt.write_text(json.dumps(dict(files=copied, prior_runtime=phase1['runtime_fingerprint']), indent=2)+'\n')
    print('Final transport source and selected installed modules synchronized.')


if __name__ == '__main__':
    main()
