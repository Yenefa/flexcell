#!/usr/bin/env python3
"""Adversarial semantics checks after updating raw-copy hashes in each temporary fixture."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from verify_core_v1 import verify


source = Path(__file__).parent / 'core-v1'
for defect in ('false_success', 'measured_zero', 'dirty_health', 'duplicate_goal', 'extra_retry', 'grant_window'):
    with tempfile.TemporaryDirectory(prefix='flexcell-core-audit-') as temp:
        root = Path(temp) / 'copy'
        shutil.copytree(source, root)
        name = 'trial-05/task.stdout'
        text = (root / name).read_text()
        task = json.loads(text.split('RESULT ', 1)[1])
        if defect == 'false_success':
            task['outcome_val'] = 0
        elif defect == 'measured_zero':
            task['final_position_error_m'] = 0.
        elif defect == 'duplicate_goal':
            task['goal_uuid'] = json.loads((root / 'trial-01/task.stdout').read_text().split('RESULT ', 1)[1])['goal_uuid']
        if defect in ('false_success', 'measured_zero', 'duplicate_goal'):
            (root / name).write_text(text.split('RESULT ', 1)[0] + 'RESULT ' + json.dumps(task) + '\n')
        elif defect == 'dirty_health':
            name = 'trial-05/health_after.stdout'
            data = json.loads((root / name).read_text()); data['checks']['carry_engaged'] = True
            (root / name).write_text(json.dumps(data))
        elif defect == 'extra_retry':
            name = 'trial-05/pick.jsonl'
            data = (root / name).read_text(); (root / name).write_text(data + data.splitlines()[0] + '\n')
        elif defect == 'grant_window':
            name = 'original_window.json'
            data = json.loads((root / name).read_text()); data['status'] = 'PASS'
            (root / name).write_text(json.dumps(data))
        manifest = json.loads((root / 'raw-copy-manifest.json').read_text())
        raw = (root / name).read_bytes()
        manifest[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
        (root / 'raw-copy-manifest.json').write_text(json.dumps(manifest))
        try:
            verify(root)
        except AssertionError:
            continue
        raise AssertionError('accepted adversarial mutation: ' + defect)
print('6 adversarial semantic mutations rejected; original archive unchanged')
