#!/usr/bin/env python3
"""Lightweight integrity/failed-outcome audit; official loader roundtrip is separate."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[3] / 'data/examples/trusted_sim_20261027'
manifest = json.loads((root / 'manifest.json').read_text())
archive = root / 'lerobot-five-episodes.zip'
assert archive.stat().st_size == manifest['archive_bytes']
assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in bundle.namelist())
    prefix = 'lerobot-five-episodes/'
    provenance_raw = bundle.read(prefix + 'flexcell_provenance.json')
    assert hashlib.sha256(provenance_raw).hexdigest() == manifest['provenance_sha256']
    provenance = json.loads(provenance_raw)
    info = json.loads(bundle.read(prefix + 'meta/info.json'))
    assert info['total_episodes'] == 5 and info['total_frames'] == 574 and info['fps'] == 10
    assert manifest['status'] == 'ROUNDTRIP_PASS' and manifest['frames'] == 574
    assert [e['runtime']['task']['outcome_val'] for e in provenance['episodes']] == [0, 0, 0, 1, 1]
    assert [e['runtime']['task']['error_code'] for e in provenance['episodes'][-2:]] == ['ERR_SKILL_FAILED', 'ERR_RECOVERY_EXHAUSTED']
    assert len({e['runtime']['runtime_fingerprint'] for e in provenance['episodes']}) == 1
    assert all(e['runtime']['expectation_met'] is True for e in provenance['episodes'])
    assert sum(e['frames'] for e in provenance['episodes']) == 574
    assert info['features']['action']['shape'] == [5]
    assert info['features']['observation.state']['shape'] == [5]
    for name in ('camera', 'state', 'reference', 'gripper'):
        assert info['features']['source.' + name + '_sim_ns']['dtype'] == 'int64'
print('Committed sample integrity PASS: 5 episodes / 574 frames; both failed outcomes retained')
