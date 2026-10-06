#!/usr/bin/env python3
"""Verify immutable bytes and the reported controller/PLACE evidence counts."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def read_rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def verify_stage(root, stage):
    folder = root / stage
    report = json.loads((folder / 'audit.json').read_text())
    deployment = json.loads((folder / 'deployment.json').read_text())
    profile = {k: v for k, v in deployment.items() if k not in ('runtime_fingerprint', 'head', 'install')}
    assert hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest() == report['runtime_fingerprint']
    batch = read_rows(folder / 'batch.jsonl')
    assert len(batch) == report['batch_rows']
    assert sum(bool(row['episode']) for row in batch)==report['episodes']
    assert all(row['runtime_fingerprint']==report['runtime_fingerprint']
               or (row['episode'] is None and row['harness_error']) for row in batch)
    assert report['physical_successes'] == sum(row['outcome']=='SUCCEEDED' and row['rc'] not in (-6,134) for row in batch)
    audits = [row['routing_audit'] for row in batch if row['routing_audit']]
    for key in ('fast_selected', 'slow_selected', 'fast_calls', 'fast_tokens'):
        assert report[key] == sum(a[key] for a in audits), key
    controller = read_rows(folder / 'raw/controller_transport.jsonl')
    by_goal = defaultdict(list)
    for row in controller:
        by_goal[row['controller_goal_uuid']].append(row)
    assert len(by_goal) == report['controller_goals']
    if report['controller_transport_ok']:
        for goal_id, events in by_goal.items():
            assert Counter(row['event'] for row in events) == Counter(controller_goal_send_requested=1, controller_goal_response=1, controller_goal_terminal=1), goal_id
            assert all(row['accepted'] for row in events if row['event']=='controller_goal_response')
            assert all(row['status'] in (4,5,6) for row in events if row['event']=='controller_goal_terminal')
            assert len({(row['request_id'], row['evidence_id']) for row in events})==1
    places = read_rows(folder / 'place.jsonl')
    checks = [c for row in places for c in row.get('release_ready_checks', [])]
    assert len(checks)==report['place_dependency_checks']
    assert sum(c['ready'] for c in checks)==report['place_checks_ready']
    assert len(read_rows(folder / 'raw/place_dependency.jsonl'))==report['negative_dependency_events']
    return dict(stage=stage, routing_ok=report['routing_ok'],
                controller_transport_ok=report['controller_transport_ok'],
                physical_successes=report['physical_successes'], episodes=report['episodes'],
                harness_errors=len(report['harness_errors']))


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'SHA256SUMS.json').read_text())
    for rel, expected in manifest.items():
        assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == expected, rel
    summaries = [verify_stage(root, stage) for stage in ('failed_batch', 'final')]
    calibration = root / 'active_calibration.json'
    calibration_sha = hashlib.sha256(calibration.read_bytes()).hexdigest()
    for stage in ('failed_batch', 'final'):
        deployment = json.loads((root / stage / 'deployment.json').read_text())
        assert deployment['active_backends']['fast']['calibration_sha256']==calibration_sha
        for rel, sha in deployment['source_sha256'].items():
            assert hashlib.sha256((root / stage / 'source' / rel).read_bytes()).hexdigest()==sha
    final_probe = json.loads((root / 'validation/local_dds_probe_final.json').read_text())
    assert final_probe['ok'] and final_probe['client_rc']==final_probe['server_rc']==0
    assert final_probe['physical_dispatches']==0
    before = json.loads((root / 'validation/clock_probe_attempt03.json').read_text())
    after = json.loads((root / 'validation/clock_probe_postbatch.json').read_text())
    assert len(before['wall_steps'])==10 and len(after['wall_steps'])==0
    print(json.dumps(dict(verified_files=len(manifest), stages=summaries,
                         clock_wall_steps_before=10, clock_wall_steps_postbatch=0), indent=2))


if __name__ == '__main__':
    main()
