#!/usr/bin/env python3
"""Read-only audit of both immutable runtimes and rejected prompt candidates."""
import hashlib
import json
from pathlib import Path

from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.contracts.metrics import wilson


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / 'SHA256SUMS.json').read_text())
    for entry in receipt:
        path = root / entry['path']
        assert path.stat().st_size == entry['bytes'], path
        assert sha(path) == entry['sha256'], path
    calibration_path = root / 'active_calibration.json'
    calibration = json.loads(calibration_path.read_text())
    assert any(b['n'] >= 5 and b['wilson_lower'] >= .85 for b in calibration['bins'])
    summaries = []
    for stage in ('phase1', 'final'):
        folder = root / stage
        deployment = json.loads((folder / 'deployment.json').read_text())
        summary = json.loads((folder / 'audit.json').read_text())
        batch = [json.loads(line) for line in (folder / 'batch.jsonl').read_text().splitlines()]
        assert len(batch) == 5 and len(list((folder / 'episodes').glob('*.json'))) == 5
        assert deployment['threshold'] == .85
        assert deployment['active_backends']['fast']['calibration_sha256'] == sha(calibration_path)
        backend_path = folder / 'source/src/flexcell/flexcell_skills/flexcell_skills/jev_backends.py'
        assert sha(backend_path) == calibration['prompt_sha256']
        for rel, digest in deployment['source_sha256'].items():
            assert sha(folder / 'source' / rel) == digest, rel
        for row in batch:
            record = json.loads((folder / 'episodes' / Path(row['episode']).name).read_text())
            assert record['runtime_fingerprint'] == deployment['runtime_fingerprint']
            result = audit_routing_episode(record, deployment)
            assert result['ok'] and result == row['routing_audit']
            assert row['rc'] not in (-6, 134)
            expected = 'SUCCEEDED' if record['final_state']['outcome'] == '0' else 'FAILED'
            assert row['outcome'] == expected
        assert summary['physical_successes'] == sum(row['outcome'] == 'SUCCEEDED' for row in batch)
        for key in ('fast_selected', 'slow_selected', 'fast_calls', 'fast_tokens'):
            assert summary[key] == sum(row['routing_audit'][key] for row in batch)
        summaries.append(dict(stage=stage, fingerprint=deployment['runtime_fingerprint'],
                              physical_successes=summary['physical_successes'], episodes=5,
                              fast_selected=summary['fast_selected'], slow_selected=summary['slow_selected']))
    assert summaries[0]['fingerprint'] != summaries[1]['fingerprint']
    for name in ('v3', 'v4'):
        folder = root / 'prompt_candidates' / name
        data = json.loads((folder / 'calibration_pilot.json').read_text())
        assert sha(folder / 'jev_backends.py') == data['prompt_sha256']
        assert data['model_sha256'] == calibration['model_sha256']
        assert data['prompt_sha256'] != calibration['prompt_sha256']
        assert json.loads((folder / 'assessment.json').read_text())['status'] == 'NOT_PROMOTED'
        for b in data['bins']:
            rows = [r for r in data['rows'] if r['partition'] == 'calibration' and r['model_success']
                    and (b['lower'] <= r['reported_confidence'] < b['upper']
                         or r['reported_confidence'] == b['upper'] == 1)]
            k, n = sum(r['agreement'] for r in rows), len(rows)
            lo, hi = wilson(k, n) if n else (0., 1.)
            assert b['n'] == n and b['agreements'] == k
            assert b['wilson_lower'] == lo and b['wilson_upper'] == hi
    probe = json.loads((root / 'run/sendgoal_probe_final.json').read_text())
    assert probe['ok'] and probe['resolved'] and probe['canceled_original_goal']
    assert probe['ros_goal_requests'] == probe['ros_goals_executed'] == 1
    print(json.dumps(dict(ok=True, frozen_files=len(receipt), stages=summaries,
                          calibration_sha256=sha(calibration_path),
                          prompt_candidates_promoted=0, actual_ros_late_acceptance_probe=True), indent=2))


if __name__ == '__main__':
    main()
