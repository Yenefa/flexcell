#!/usr/bin/env python3
"""Back up a small runtime delta and activate WSL-local DDS discovery."""
import hashlib
import json
from pathlib import Path
import shutil


def main():
    task = Path('/home/ros/.codex/worktrees/16d1/flexcell')
    workspace, win = Path('/home/ros/agentic_workcell_ws'), Path('/mnt/c/dev/flexcell')
    logs = Path('/home/ros/fc_sync_logs/place_transport_20261006')
    receipt = logs / 'activation.json'
    assert not receipt.exists(), 'Preserve activation evidence'
    files = ['src/flexcell/flexcell_skills/flexcell_skills/move_to_pose_server.py',
             'src/flexcell/flexcell_skills/flexcell_skills/place_server.py',
             'src/flexcell/flexcell_skills/test/test_controller_transport.py',
             'src/flexcell/flexcell_skills/test/test_place_dependency.py',
             'setup/124_local_dds_probe.py', 'setup/cyclone_wsl_local.xml']
    for rel in files:
        target, previous = workspace / rel, win / rel
        assert target.exists() == previous.exists(), rel
        if target.exists():
            assert target.read_bytes() == previous.read_bytes(), 'Concurrent change: ' + rel
    copied = []
    installed = Path('/home/ros/.local/share/flexcell/mainline/install/flexcell_skills/lib/python3.12/site-packages/flexcell_skills')
    prefix = 'src/flexcell/flexcell_skills/flexcell_skills/'
    for rel in files:
        target = workspace / rel
        if target.exists():
            backup = logs / 'backup/source' / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(task / rel, target)
        if rel.startswith(prefix):
            runtime = installed / rel[len(prefix):]
            backup = logs / 'backup/installed' / rel[len(prefix):]
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime, backup)
            shutil.copy2(task / rel, runtime)
            assert runtime.read_bytes() == target.read_bytes()
        copied.append(dict(path=rel, sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    profile = Path('/home/ros/.config/flexcell/mainline_physics.sh')
    text = profile.read_text()
    assert text.count('export FLEXCELL_DDS_PROFILE=') == 1
    backup = logs / 'backup/mainline_physics.sh'
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(profile, backup)
    lines = [line if not line.startswith('export FLEXCELL_DDS_PROFILE=') else
             'export FLEXCELL_DDS_PROFILE=/home/ros/agentic_workcell_ws/setup/cyclone_wsl_local.xml'
             for line in text.splitlines()]
    profile.write_text('\n'.join(lines) + '\n')
    receipt.write_text(json.dumps(dict(files=copied, profile=str(profile), profile_backup=str(backup),
        dds_profile='/home/ros/agentic_workcell_ws/setup/cyclone_wsl_local.xml',
        ros_domain_id=45, rmw='rmw_cyclonedds_cpp', calibrated_model_unchanged=True), indent=2)+'\n')
    print('Selected skills modules synchronized; local DDS profile activated with backup.')


if __name__ == '__main__':
    main()
