#!/usr/bin/env python3
"""Audit the new live episode and flat decisions against frozen deployment."""
import hashlib
import json
from pathlib import Path
import re

from flexcell_skills.confidence_calibration import ConfidenceCalibration, prompt_digest
from flexcell_skills.contracts.episode import _sanitize
from flexcell_skills.contracts.metrics import latency_summary
from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.jev_backends import make_backend
from flexcell_skills.jev_policy import JevPolicy


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path('/home/ros/fc_sync_logs/clef_route_20261006')
    repo = Path('/home/ros/agentic_workcell_ws')
    before = json.loads((root / 'before_smoke.json').read_text())
    paths = [p for p in (Path.home() / '.ros/flexcell/episodes').glob('*.json')
             if str(p) not in before['episodes']]
    assert len(paths) == 1, paths
    episode = json.loads(paths[0].read_text())
    deployed = re.findall(r'DEPLOYED .* logs=(.+)', (root / 'deploy.log').read_text())
    assert len(deployed) == 1
    runtime = Path(deployed[0])
    deployment = json.loads((runtime / 'deployment.json').read_text())
    calibration = ConfidenceCalibration()
    assert calibration.error == '' and calibration.sha256
    assert JevPolicy(make_backend('clef')).route_eligible(.85)
    assert deployment['threshold'] == .85
    assert deployment['ros_domain_id'] == 45
    assert deployment['rmw_implementation'] == 'rmw_cyclonedds_cpp'
    assert deployment['active_backends']['fast']['calibration_sha256'] == calibration.sha256
    assert digest(root / 'calibration_assembled.json') == calibration.sha256
    assert deployment['head'] == 'ffde775a0ef9d1cb0f6a3b39436fbe1f97927370'
    verified = {}
    for rel, expected in {**deployment['source_sha256'],
                          **deployment['harness_sha256']}.items():
        assert digest(repo / rel) == expected, rel
        verified[rel] = expected
    fleet = (runtime / 'fleet.log').read_text()
    assert "jev backend 'clef' unavailable" not in fleet
    assert (root / 'deploy.rc').read_text().strip() == '0'
    smoke_rc = int((root / 'smoke.rc').read_text())
    assert smoke_rc not in (-6, 134), 'SIGABRT is never accepted'
    reset_text = (root / 'smoke/llm_single_reset.json').read_text()
    reset = json.JSONDecoder().raw_decode(reset_text.lstrip())[0]
    assert reset['ok'] is True
    audit = audit_routing_episode(episode, deployment)
    assert audit['ok'], audit
    assert str(episode['final_state']['outcome']) == '0', episode['final_state']
    assert episode['final_state']['error_code'] == 0
    assert audit['fast_selected'] > 0 and audit['fast_tokens'] > 0
    decisions_path = Path.home() / '.ros/flexcell/decisions.jsonl'
    with decisions_path.open('rb') as stream:
        stream.seek(before['decisions_bytes'])
        new_decisions = stream.read()
    snapshot = root / 'decisions_smoke.jsonl'
    if snapshot.exists():
        assert snapshot.read_bytes() == new_decisions
    else:
        snapshot.write_bytes(new_decisions)
    flat = [json.loads(line) for line in new_decisions.splitlines() if line]
    assert len(flat) == len(episode['steps'])
    decisions = []
    for row, step in zip(flat, episode['steps']):
        assert row['run_id'] == episode['run_id']
        assert row['seq'] == step['seq']
        decision = step['policy_output']
        for field in ('action', 'target', 'confidence', 'policy_trace'):
            # Episode serialization rounds every float to nine decimal places.
            assert _sanitize(row[field]) == decision[field]
        trace = row['policy_trace']
        fast = [p for p in trace['proposals'] if p['policy'] == 'jev']
        for p in fast:
            assert not p.get('skipped')
            assert p['policy_trace']['fallback'] is False
            assert p['policy_trace']['tokens'] > 0
        decisions.append(dict(seq=row['seq'], action=row['action'],
                              source=trace['source'], fallback=trace['fallback'],
                              fast_tokens=sum(p['policy_trace']['tokens'] for p in fast),
                              confidence=row['confidence']))
    measured = [step['decide_latency_ms'] for step in episode['steps']
                if step['policy_input']['world_state_canonical'] is not None]
    assert all(step['decide_latency_clock'] == 'perf_counter_ns'
               for step in episode['steps'])
    assert all(type(value) is float and value > 0 for value in measured)
    result = dict(schema_version=1, ok=True, episode_file=str(paths[0]),
                  episode_sha256=digest(paths[0]), run_id=episode['run_id'],
                  runtime=str(runtime), runtime_fingerprint=deployment['runtime_fingerprint'],
                  calibration_sha256=calibration.sha256, prompt_sha256=prompt_digest(),
                  route_eligible_085=True, threshold=.85, deploy_rc=0,
                  smoke_command_rc=smoke_rc, reset_ok=reset['ok'],
                  final_state=episode['final_state'], routing_audit=audit,
                  flat_decisions=decisions, source_files_verified=len(verified),
                  decision_latency=dict(status='MEASURED', clock='perf_counter_ns',
                                        bootstrap_excluded=True,
                                        **latency_summary(measured)),
                  scope='Single-object live routing smoke; no physical-success-rate estimate')
    assert not (root / 'live_audit_verified.json').exists()
    (root / 'live_audit_verified.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
