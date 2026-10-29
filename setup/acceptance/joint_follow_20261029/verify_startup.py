#!/usr/bin/env python3
"""Verify the retained startup failure and non-simulation EGL probes offline."""
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def verify(root):
    root = Path(root).resolve()
    inputs = root / 'inputs.json'
    require(hashlib.sha256(inputs.read_bytes()).hexdigest() ==
            '7d9f4b7ebc5b414a91966f456616323b5fdc12c4f437ca5887a24920d375978c',
            'input manifest changed')
    for relative, expected in json.loads(inputs.read_text())['files_sha256'].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root) and path.is_file(), 'missing or unsafe input: ' + relative)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'changed input: ' + relative)
    window = json.loads((root / 'startup_629e496/window.json').read_text())
    require(window['status'] == 'STOPPED' and window['no_replacements'] is True and
            len(window['episodes']) == 1, 'startup must remain a stopped one-trial window')
    result = window['episodes'][0]['result']
    require(result['physical_tasks_dispatched'] == 0 and result['status'] == 'HARNESS_ERROR' and
            'timed out' in result['error'] and 'task' not in result,
            'startup failure must not be reported as a task result')
    runs = list((root / 'startup_629e496/trial-01').glob('run-*'))
    require(len(runs) == 1 and not (root / 'startup_629e496/trial-02').exists(),
            'unexpected extra trial')
    run = runs[0]
    require(not (run / 'task.stdout').exists() and not (run / 'physics_steps.jsonl').read_bytes(),
            'unexpected task dispatch or physics observations')
    identity = json.loads((run / 'identity.stdout').read_text())
    require(identity['source_revision'] == '629e49679ccef5484e030506b3c0ee3dc175e0a5' and
            identity['mismatches'] == [], 'source/install identity changed')
    log = (run / 'stack.log').read_text()
    require('Unable to load Ogre Plugin' in log and 'Segmentation fault' in log,
            'original rendering failure is missing')
    negative = json.loads((root / 'egl_negative/camera_preflight.json').read_text())
    positive = json.loads((root / 'egl_positive/camera_preflight.json').read_text())
    require(negative['status'] == 'FAIL' and positive['status'] == 'PASS' and
            negative['simulator_started'] is positive['simulator_started'] is False,
            'non-simulation EGL probe outcomes changed')
    require(positive['vendor_files']['/usr/share/glvnd/egl_vendor.d/50_mesa.json'] ==
            'cd3881df4227c13ca7f9cfe6c78820f21d5f7a00a41b299214f6f827e63be369',
            'restored Mesa vendor file differs')
    return dict(status='STARTUP_FAILURE_RETAINED', window_id=window['window_id'],
                physical_tasks_dispatched=0, follow_qualified=False,
                controlled_egl_negative='FAIL', restored_egl_positive='PASS')


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parent), indent=2))
