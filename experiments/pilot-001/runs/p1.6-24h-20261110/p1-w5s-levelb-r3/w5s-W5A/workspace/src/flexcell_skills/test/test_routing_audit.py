from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from flexcell_skills.contracts.routing_audit import audit_routing_episode


def episode():
    fast = dict(source='jev', fallback=False, model='q8', model_sha256='weights',
                calibration='cal', calibration_sha256='cal',
                confidence_calibrated=True, tokens=400)
    return dict(runtime_fingerprint='runtime', steps=[dict(seq=1,
        policy_input=dict(world_state_canonical='{}'),
        policy_output=dict(policy_trace=dict(source='jev', fallback=False,
            threshold=.85, calibration_sha256='cal', proposals=[dict(
                policy='jev', fallback=False, policy_trace=fast)])))])


def audit(record):
    return audit_routing_episode(record, dict(runtime_fingerprint='runtime',
        threshold=.85, active_backends=dict(fast=dict(model='q8',
            model_sha256='weights', calibration_sha256='cal'))))


def test_accepted_route_is_counted_once_per_episode():
    report = audit(episode())
    assert report['ok'] and report['fast_selected'] == 1
    assert report['fast_calls'] == 1 and report['fast_tokens'] == 400


def test_zero_tokens_cannot_pass_as_real_model_execution():
    record = episode()
    record['steps'][0]['policy_output']['policy_trace']['proposals'][0]['policy_trace']['tokens'] = 0
    assert not audit(record)['ok']


def test_mixed_calibration_is_rejected_even_if_selected_source_is_slow():
    record = episode()
    trace = record['steps'][0]['policy_output']['policy_trace']
    trace['source'] = 'llm'
    trace['proposals'][0]['policy_trace']['calibration_sha256'] = 'old-calibration'
    assert not audit(record)['ok']


def test_sparse_fast_bin_may_escalate_but_not_authorize_fast_selection():
    record = episode()
    trace = record['steps'][0]['policy_output']['policy_trace']
    trace['source'] = 'llm'
    fast = trace['proposals'][0]['policy_trace']
    fast.update(calibration='insufficient_bin_samples', confidence_calibrated=False)
    assert audit(record)['ok']
    trace['source'] = 'jev'
    assert not audit(record)['ok']


def test_bootstrap_is_not_in_the_model_denominator():
    record = episode()
    bootstrap = deepcopy(record['steps'][0])
    bootstrap['seq'] = 0
    bootstrap['policy_input']['world_state_canonical'] = None
    bootstrap['policy_output']['policy_trace'].update(
        source='fsm', fallback=True, failure='bootstrap', proposals=[])
    record['steps'].insert(0, bootstrap)
    report = audit(record)
    assert report['ok'] and report['bootstrap'] == 1 and report['model_decisions'] == 1


def test_runtime_threshold_and_weight_drift_each_fail_closed():
    for key, value in (('runtime_fingerprint', 'other'),):
        record = episode()
        record[key] = value
        assert not audit(record)['ok']
    record = episode()
    record['steps'][0]['policy_output']['policy_trace']['threshold'] = .03
    assert not audit(record)['ok']
    record = episode()
    record['steps'][0]['policy_output']['policy_trace']['proposals'][0]['policy_trace']['model_sha256'] = 'other'
    assert not audit(record)['ok']


def runner_module():
    path = Path(__file__).resolve().parents[4] / 'setup/94_scenario_runner.py'
    spec = importlib.util.spec_from_file_location('routing_runner_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hybrid_runner_refuses_missing_manifest_before_ros_dispatch(monkeypatch):
    runner = runner_module()
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'hybrid', '--batch', 'S1:1'])
    monkeypatch.setattr(runner, 'run_episode', lambda *a, **k: pytest.fail('ROS dispatched'))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2


def test_legacy_smoke_without_routing_audit_does_not_unlock_baseline(tmp_path, monkeypatch):
    runner = runner_module()
    deployment = tmp_path / 'deployment.json'
    deployment.write_text(json.dumps(dict(policy='hybrid', runtime_fingerprint='runtime')))
    smoke = tmp_path / 'smoke.jsonl'
    row = dict(scenario='S1', protocol_sha256=runner.PROTOCOL_SHA256,
        runtime_fingerprint='runtime', policy='hybrid', stage='smoke',
        scenario_exercised=True, harness_error=None, outcome='SUCCEEDED',
        expected='SUCCEEDED', model_decisions=7)
    smoke.write_text('\n'.join(json.dumps(row) for _ in range(5)))
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'hybrid', '--batch', 'S1:20',
        '--stage', 'baseline', '--deployment', str(deployment), '--smoke-summary', str(smoke)])
    monkeypatch.setattr(runner, 'run_episode', lambda *a, **k: pytest.fail('ROS dispatched'))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
