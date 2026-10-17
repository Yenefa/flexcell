"""Hybrid benchmark qualification must include real fast-model calls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from flexcell_skills.contracts import routing_audit


def deployment():
    return dict(policy='hybrid', runtime_fingerprint='runtime', threshold=.85,
                active_backends=dict(fast=dict(model='q8', model_sha256='weights',
                                                calibration_sha256='cal')))


def episode(mode='fast'):
    fast = dict(source='jev', fallback=False, model='q8', model_sha256='weights',
                calibration='cal', calibration_sha256='cal',
                confidence_calibrated=True, tokens=400)
    trace = dict(source='jev' if mode == 'fast' else 'llm', fallback=False,
                 threshold=.85, calibration_sha256='cal',
                 proposals=[dict(policy='jev', policy_trace=fast)])
    if mode == 'skipped':
        trace['proposals'] = [dict(policy='jev', skipped=True)]
    elif mode == 'missing':
        trace['proposals'] = []
    return dict(runtime_fingerprint='runtime', steps=[dict(seq=1,
        policy_input=dict(world_state_canonical='{}'),
        policy_output=dict(policy_trace=trace))])


def row(mode='fast'):
    return dict(policy='hybrid', runtime_fingerprint='runtime', scenario='S1',
                outcome='SUCCEEDED', harness_error=None,
                routing_audit=routing_audit.audit_routing_episode(episode(mode), deployment()))


@pytest.mark.parametrize('mode', ['skipped', 'missing'])
def test_no_real_fast_model_call_cannot_qualify_a_hybrid_episode(mode):
    report = routing_audit.audit_routing_episode(episode(mode), deployment())
    assert report['fast_calls'] == 0 and report['model_decisions'] == 1
    assert not report['ok']
    assert any('no real fast' in reason for reason in report['errors'])


def test_real_fast_proposal_may_escalate_every_decision_to_slow():
    report = routing_audit.audit_routing_batch([row('slow'), row('slow')], deployment())
    assert report['ok'], report['errors']
    assert report['fast_calls'] == 2 and report['fast_tokens'] == 800
    assert report['fast_selected'] == 0 and report['slow_selected'] == 2
    assert report['calibration_sha256'] == 'cal'


@pytest.mark.parametrize('change', ['empty', 'zero', 'calibration', 'fingerprint',
                                   'missing_audit', 'failed_audit', 'harness',
                                   'negative_count', 'boolean_count'])
def test_invalid_batch_provenance_fails_closed(change):
    rows = [row()]
    if change == 'empty':
        rows = []
    elif change == 'zero':
        rows[0]['routing_audit'].update(fast_calls=0, fast_tokens=0)
    elif change == 'calibration':
        rows[0]['routing_audit']['calibration_sha256'] = 'other'
    elif change == 'fingerprint':
        rows[0]['runtime_fingerprint'] = 'other'
    elif change == 'missing_audit':
        rows[0].pop('routing_audit')
    elif change == 'failed_audit':
        rows[0]['routing_audit']['ok'] = False
    elif change == 'harness':
        rows[0]['outcome'] = 'HARNESS_ERROR'
        rows[0]['harness_error'] = 'reset failed'
    else:
        rows[0]['routing_audit']['fast_calls'] = -1 if change == 'negative_count' else True
    report = routing_audit.audit_routing_batch(rows, deployment())
    assert not report['ok'] and report['errors']


def test_one_good_episode_cannot_hide_a_later_missing_fast_arm():
    stale = row()
    stale['routing_audit'].update(fast_calls=0, fast_tokens=0)
    report = routing_audit.audit_routing_batch([row(), stale], deployment())
    assert not report['ok']


def runner_module():
    path = Path(__file__).resolve().parents[4] / 'setup/94_scenario_runner.py'
    spec = importlib.util.spec_from_file_location('batch_routing_runner_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_runner(tmp_path, monkeypatch, modes, policy='hybrid'):
    runner = runner_module()
    store = tmp_path / 'episodes'
    store.mkdir()
    manifest = tmp_path / 'deployment.json'
    manifest.write_text(json.dumps(deployment()))
    monkeypatch.setattr(runner, 'EPISODE_DIR', str(store))
    argv = ['runner', '--policy', policy, '--batch', 'S1:3']
    if policy == 'hybrid':
        argv += ['--deployment', str(manifest)]
    monkeypatch.setattr(sys, 'argv', argv)
    dispatched = []

    def run_episode(*args, **kwargs):
        index = len(dispatched)
        mode = modes[index]
        dispatched.append(mode)
        record = episode(mode)
        evidence_id = 'result-%d' % index
        record.update(policy=dict(name=policy),
                      benchmark_protocol=dict(sha256=runner.PROTOCOL_SHA256),
                      final_state=dict(evidence_id=evidence_id, outcome='SUCCEEDED'))
        (store / ('episode-%d.json' % index)).write_text(json.dumps(record))
        return 0, 'RESULT ' + json.dumps(dict(outcome='OUTCOME_SUCCEEDED',
                                             evidence_id=evidence_id)), {}

    monkeypatch.setattr(runner, 'run_episode', run_episode)
    return runner, store, dispatched


def test_runner_stops_after_fast_arm_disappears_and_preserves_evidence(tmp_path, monkeypatch, capsys):
    runner, store, dispatched = configure_runner(tmp_path, monkeypatch, ['slow', 'skipped', 'fast'])
    assert runner.main() == 1
    assert dispatched == ['slow', 'skipped']
    rows = [json.loads(line) for line in next(store.glob('batch_*.jsonl')).read_text().splitlines()]
    assert [item['outcome'] for item in rows] == ['SUCCEEDED', 'HARNESS_ERROR']
    assert json.loads((store / 'episode-1.json').read_text())['final_state']['outcome'] == 'SUCCEEDED'
    batch = json.loads(next((store / 'batch_audits').glob('*.json')).read_text())
    assert not batch['routing_audit']['ok']
    assert 'HARNESS_ERROR' in capsys.readouterr().out


def test_runner_accepts_real_fast_calls_with_only_slow_selections(tmp_path, monkeypatch):
    runner, store, dispatched = configure_runner(tmp_path, monkeypatch, ['slow'] * 3)
    assert runner.main() == 0
    assert len(dispatched) == 3
    batch = json.loads(next((store / 'batch_audits').glob('*.json')).read_text())
    assert batch['routing_audit']['ok']
    assert batch['routing_audit']['fast_calls'] == 3
    assert batch['routing_audit']['fast_selected'] == 0
    # The sidecar cannot be mistaken for an episode by existing *.json readers.
    assert len(list(store.glob('*.json'))) == 3


def test_fsm_control_does_not_require_a_fast_arm(tmp_path, monkeypatch):
    runner, store, dispatched = configure_runner(tmp_path, monkeypatch, ['missing'] * 3, policy='fsm')
    monkeypatch.setattr(runner, 'replay_episode', lambda *args: [dict(ok=True)])
    assert runner.main() == 0
    assert len(dispatched) == 3
    assert not (store / 'batch_audits').exists()


@pytest.mark.parametrize('field', ['runtime_fingerprint', 'model', 'model_sha256', 'calibration_sha256'])
def test_incomplete_hybrid_manifest_is_rejected_before_dispatch(tmp_path, monkeypatch, field):
    runner = runner_module()
    manifest = deployment()
    (manifest if field == 'runtime_fingerprint' else manifest['active_backends']['fast']).pop(field)
    path = tmp_path / 'deployment.json'
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'hybrid', '--batch', 'S1:1',
                                    '--deployment', str(path)])
    monkeypatch.setattr(runner, 'run_episode', lambda *a, **k: pytest.fail('ROS dispatched'))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2


@pytest.mark.parametrize('threshold', ['missing', None, True, False, '0.85',
                                     -.01, 1.01, 10 ** 400, -(10 ** 400), float('nan'),
                                     float('inf'), -float('inf')])
def test_invalid_threshold_is_rejected_before_dispatch(tmp_path, monkeypatch, threshold):
    runner, store, dispatched = configure_runner(tmp_path, monkeypatch, ['fast'])
    path = tmp_path / 'deployment.json'
    manifest = deployment()
    if threshold == 'missing':
        manifest.pop('threshold')
    else:
        manifest['threshold'] = threshold
    path.write_text(json.dumps(manifest))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert dispatched == []
    assert list(store.iterdir()) == []


@pytest.mark.parametrize('threshold', [0, .03, .85, 1])
def test_valid_threshold_reaches_dispatch(tmp_path, monkeypatch, threshold):
    runner, _, _ = configure_runner(tmp_path, monkeypatch, ['fast'])
    path = tmp_path / 'deployment.json'
    manifest = deployment()
    manifest['threshold'] = threshold
    path.write_text(json.dumps(manifest))

    class DispatchReached(Exception):
        pass

    def stop_before_transport(*args, **kwargs):
        raise DispatchReached

    monkeypatch.setattr(runner, 'run_episode', stop_before_transport)
    with pytest.raises(DispatchReached):
        runner.main()


@pytest.mark.parametrize('mode', ['zero', 'calibration'])
def test_smoke_with_invalid_fast_provenance_cannot_unlock_baseline(tmp_path, monkeypatch, mode):
    runner = runner_module()
    manifest = tmp_path / 'deployment.json'
    manifest.write_text(json.dumps(deployment()))
    smoke = tmp_path / 'smoke.jsonl'
    record = row('slow')
    record.update(protocol_sha256=runner.PROTOCOL_SHA256, stage='smoke',
                  scenario_exercised=True, expected='SUCCEEDED', model_decisions=1)
    if mode == 'zero':
        record['routing_audit'].update(fast_calls=0, fast_tokens=0)
    else:
        record['routing_audit']['calibration_sha256'] = 'other'
    smoke.write_text('\n'.join(json.dumps(deepcopy(record)) for _ in range(5)))
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'hybrid', '--batch', 'S1:20',
                                    '--stage', 'baseline', '--deployment', str(manifest),
                                    '--smoke-summary', str(smoke)])
    monkeypatch.setattr(runner, 'run_episode', lambda *a, **k: pytest.fail('ROS dispatched'))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
