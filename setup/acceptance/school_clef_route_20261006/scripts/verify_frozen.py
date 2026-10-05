#!/usr/bin/env python3
"""Read-only verification of frozen bytes and routing, including failed runs."""
import hashlib
import json
from pathlib import Path

from flexcell_skills.contracts.metrics import wilson
from flexcell_skills.contracts.routing_audit import audit_routing_episode


def main():
    archive = Path(__file__).resolve().parents[1]
    receipt = json.loads((archive / 'SHA256SUMS.json').read_text())
    for row in receipt:
        data = (archive / row['copy']).read_bytes()
        assert len(data) == row['bytes'], row['copy']
        assert hashlib.sha256(data).hexdigest() == row['sha256'], row['copy']
    deployment = json.loads((archive / 'deployment.json').read_text())
    calibration_path = archive / 'run/calibration_assembled.json'
    calibration = json.loads(calibration_path.read_text())
    digest = hashlib.sha256(calibration_path.read_bytes()).hexdigest()
    assert deployment['active_backends']['fast']['calibration_sha256'] == digest
    for b in calibration['bins']:
        rows = [r for r in calibration['rows'] if r['partition'] == 'calibration'
                and r['model_success'] and
                (b['lower'] <= r['reported_confidence'] < b['upper'] or
                 r['reported_confidence'] == b['upper'] == 1)]
        assert b['n'] == len(rows)
        assert b['agreements'] == sum(r['agreement'] for r in rows)
        lo, hi = wilson(b['agreements'], b['n']) if rows else (0., 1.)
        assert b['wilson_lower'] == lo and b['wilson_upper'] == hi
    audits = []
    for path in sorted((archive / 'episodes').glob('*.json')):
        record = json.loads(path.read_text())
        audit = audit_routing_episode(record, deployment)
        assert audit['ok'], (path, audit)
        assert audit['fast_selected'] > 0 and audit['fast_tokens'] > 0
        audits.append(dict(episode=path.name, final_state=record['final_state'], **audit))
    assert len(audits) == 6
    summary = json.loads((archive / 'run/s1_n5_audit.json').read_text())
    assert summary['counts']['episodes'] == 5
    assert summary['routing_ok']
    assert any(b['n'] >= 5 and b['wilson_lower'] >= .85 for b in calibration['bins'])
    print(json.dumps(dict(frozen_files_verified=len(receipt),
                          calibration_sha256=digest, route_eligible_085=True,
                          live_episodes_verified=len(audits),
                          s1_n5_counts=summary['counts']), indent=2))


if __name__ == '__main__':
    main()
