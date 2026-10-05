"""Read frozen bytes and recompute routing evidence for every completed batch."""
import hashlib
import json
from pathlib import Path
import re

from flexcell_skills.contracts.routing_audit import audit_routing_episode

repo = Path('/home/ros/agentic_workcell_ws')
root = repo / 'setup/acceptance/q8_teardown_20261005'
archive = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/setup/acceptance/q8_teardown_20261005')
receipt = json.loads((archive / 'SHA256SUMS.json').read_text())
for row in receipt:
    original, frozen = Path(row['original']), archive / row['copy']
    data = frozen.read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['sha256'], row['copy']
    assert len(data) == row['bytes']
    assert original.read_bytes() == data, row['original']

deployments = {}
for path in root.glob('deployment*.json'):
    data = json.loads(path.read_text())
    deployments[data['runtime_fingerprint']] = data

latest_path = max(root.glob('deployment*.json'), key=lambda p:p.stat().st_mtime)
latest = json.loads(latest_path.read_text())
source_verified = {}
for rel, expected in {**latest['source_sha256'], **latest['harness_sha256']}.items():
    actual = hashlib.sha256((repo / rel).read_bytes()).hexdigest()
    assert actual == expected, rel
    source_verified[rel] = actual
calibration = Path('/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json')
assert hashlib.sha256(calibration.read_bytes()).hexdigest() == latest['active_backends']['fast']['calibration_sha256']

results = []
for log in sorted(root.glob('*.log')):
    if not re.match(r'(smoke|baseline)_[0-9.]+_\d+_', log.name):
        continue
    paths = re.findall(r'batch summary: (.+)', log.read_text())
    if not paths:
        continue
    batch = Path(paths[-1])
    rows = [json.loads(line) for line in batch.read_text().splitlines() if line]
    counts = dict(episodes=0, bootstrap=0, fast_selected=0, slow_selected=0,
                  fast_calls=0, fast_tokens=0, harness_errors=0, failures=0)
    fingerprints = set()
    failed_runs = []
    for row in rows:
        if row['outcome'] == 'HARNESS_ERROR':
            counts['harness_errors'] += 1
        if not row.get('episode'):
            assert row['outcome'] == 'HARNESS_ERROR'
            continue
        record = json.loads(Path(row['episode']).read_text())
        fingerprint = record['runtime_fingerprint']
        fingerprints.add(fingerprint)
        fresh = audit_routing_episode(record, deployments[fingerprint])
        assert fresh == row['routing_audit'], (batch, row['run'], fresh)
        assert fresh['ok'], (batch, row['run'], fresh['errors'])
        assert row['model_decisions'] == fresh['model_decisions']
        counts['episodes'] += 1
        for field in ('bootstrap', 'fast_selected', 'slow_selected', 'fast_calls', 'fast_tokens'):
            counts[field] += fresh[field]
        if row['outcome'] == 'FAILED':
            counts['failures'] += 1
            failed_runs.append(dict(run=row['run'], episode=row['episode'],
                                   final_state=record['final_state']))
    assert len(fingerprints) <= 1, batch
    results.append(dict(batch=str(batch), log=str(log), fingerprints=sorted(fingerprints),
                        **counts, failed_runs=failed_runs))

result = dict(frozen_originals=len(receipt), exact_byte_verification=True,
              routing_recomputed=True, source_verified=source_verified,
              current_deployment=str(latest_path), calibration_sha256=latest['active_backends']['fast']['calibration_sha256'],
              groups=results)
target = root / 'verification_final.json'
assert not target.exists(), 'Choose a new name instead of overwriting verification evidence'
target.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({**{k:v for k,v in result.items() if k not in ('source_verified', 'groups')},
                  'source_files_verified':len(source_verified),
                  'groups': [{k:v for k,v in r.items() if k != 'failed_runs'} for r in results]}, indent=2))
