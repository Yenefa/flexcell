"""Synthetic admission tests: no model calls, ROS clients or robot actions."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

from flexcell_skills.contracts.benchmark_protocol import load_protocol
from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.contracts.smoke_window import (
    encode_plan, make_batch_plan, qualify_smoke_window)


PROTOCOL, DIGEST = load_protocol()
DEPLOYMENT = dict(policy='hybrid', runtime_fingerprint='runtime', threshold=.85,
                  active_backends=dict(fast=dict(model='q8', model_sha256='weights',
                                                  calibration_sha256='cal')))


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def make_window(root, counts=None, policy='fsm'):
    root.mkdir(parents=True, exist_ok=True)
    counts = counts or [('S1', 5)]
    deployment = DEPLOYMENT if policy == 'hybrid' else None
    plan = make_batch_plan('batch_fixture', counts, policy, 'smoke', 100,
                          PROTOCOL, DIGEST, deployment)
    plan_bytes = encode_plan(plan)
    plan_dir = root / 'batch_plans'
    plan_dir.mkdir()
    (plan_dir / 'batch_fixture.json').write_bytes(plan_bytes)
    rows = []
    for index, slot in enumerate(plan['schedule']):
        evidence = 'evidence-%s' % index
        rc = 0 if slot['expected'] == 'SUCCEEDED' else 1
        record = dict(EpisodeSchemaVersion=1, runtime_fingerprint='runtime', policy=dict(name=policy),
                      benchmark_protocol=dict(sha256=DIGEST),
                      final_state=dict(evidence_id=evidence, outcome=str(rc),
                                       error_code=0 if rc == 0 else 50), steps=[])
        if policy == 'hybrid':
            fast = dict(source='jev', fallback=False, model='q8', model_sha256='weights',
                        calibration_sha256='cal', confidence_calibrated=False,
                        calibration='insufficient_bin_samples', tokens=100)
            record['steps'] = [dict(seq=1, policy_input=dict(world_state_canonical='{}'),
                policy_output=dict(policy_trace=dict(source='llm', fallback=False,
                    threshold=.85, calibration_sha256='cal', proposals=[
                        dict(policy='jev', fallback=False, policy_trace=fast)])))]
        episode = root / ('episode-%s.json' % index)
        episode.write_text(json.dumps(record))
        rows.append(dict(slot, batch_id=plan['batch_id'],
                         batch_plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
                         stage='smoke', policy=policy, protocol_id=PROTOCOL['protocol_id'],
                         protocol_sha256=DIGEST, runtime_fingerprint='runtime',
                         scenario_exercised=True, harness_error=None,
                         outcome=slot['expected'], rc=rc, replay_ok=policy == 'fsm',
                         model_decisions=0 if policy == 'fsm' else 1,
                         episode=str(episode), episode_relative=episode.name,
                         episode_sha256=hashlib.sha256(episode.read_bytes()).hexdigest(),
                         evidence_id=evidence,
                         routing_audit=audit_routing_episode(record, deployment)
                         if deployment else None))
    summary = root / 'batch_fixture.jsonl'
    write_rows(summary, rows)
    return summary, rows, plan


def qualify(summary, required=None, policy='fsm', deployment=None):
    return qualify_smoke_window(summary, required or ['S1'], policy, PROTOCOL, DIGEST, deployment)


def runner_module():
    path = Path(__file__).resolve().parents[4] / 'setup/94_scenario_runner.py'
    spec = importlib.util.spec_from_file_location('fixed_smoke_runner_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complete_round_robin_window_includes_expected_failures(tmp_path):
    summary, rows, plan = make_window(tmp_path, [('S1', 5), ('S5', 5)])
    assert [slot['scenario'] for slot in plan['schedule']] == ['S1', 'S5'] * 5
    assert [row['seed'] for row in rows] == list(range(100, 110))
    assert rows[1]['outcome'] == 'FAILED'
    fingerprint, accepted = qualify(summary, ['S1', 'S5'])
    assert fingerprint == 'runtime' and accepted == rows


@pytest.mark.parametrize('change', ['pooled', 'clipped', 'extra', 'failed-unrequested'])
def test_success_subset_cannot_qualify_a_larger_or_failed_window(tmp_path, change):
    counts = [('S1', 10)] if change in ('pooled', 'clipped') else [('S1', 5), ('S5', 5)]
    summary, rows, _ = make_window(tmp_path, counts)
    if change == 'pooled':
        rows[0]['outcome'] = rows[1]['outcome'] = 'FAILED'  # Eight good rows still cannot qualify.
    elif change == 'clipped':
        rows = rows[5:]  # Keeping exactly five good rows does not change the declared plan.
    elif change == 'extra':
        rows.append(deepcopy(rows[0]))
    else:
        rows[1]['outcome'] = 'SUCCEEDED'  # A requested S1 subset cannot hide failed S5 checks.
    write_rows(summary, rows)
    with pytest.raises(ValueError):
        qualify(summary)


@pytest.mark.parametrize('key,value', [
    ('outcome', 'FAILED'), ('harness_error', 'reset failure'),
    ('scenario_exercised', 1), ('replay_ok', False), ('seed', True),
    ('run', 2), ('rc', 6), ('rc', False), ('batch_id', 'other'), ('batch_plan_sha256', 'other'),
    ('protocol_sha256', 'other'), ('policy', 'jev'),
    ('runtime_fingerprint', 'other'), ('runtime_fingerprint', None),
])
def test_every_row_must_match_the_window_and_pass_its_checks(tmp_path, key, value):
    summary, rows, _ = make_window(tmp_path)
    rows[2][key] = value
    write_rows(summary, rows)
    with pytest.raises(ValueError):
        qualify(summary)


@pytest.mark.parametrize('change', ['path', 'evidence', 'hash', 'missing', 'identity'])
def test_native_evidence_is_unique_present_and_unchanged(tmp_path, change):
    summary, rows, _ = make_window(tmp_path)
    if change == 'path':
        rows[1]['episode_relative'] = rows[0]['episode_relative']
    elif change == 'evidence':
        rows[1]['evidence_id'] = rows[0]['evidence_id']
    elif change == 'hash':
        (tmp_path / rows[1]['episode_relative']).write_text('{}')
    elif change == 'missing':
        (tmp_path / rows[1]['episode_relative']).unlink()
    else:
        rows[1]['evidence_id'] = 'wrong-native-identity'
    write_rows(summary, rows)
    with pytest.raises((ValueError, OSError)):
        qualify(summary)


def test_moved_batch_uses_local_native_bytes_instead_of_stale_absolute_paths(tmp_path):
    original = tmp_path / 'original'
    summary, rows, _ = make_window(original)
    copied = tmp_path / 'copied'
    shutil.copytree(original, copied)
    assert qualify(copied / summary.name)[0] == 'runtime'
    (copied / rows[0]['episode_relative']).write_text('{}')
    with pytest.raises(ValueError, match='SHA'):
        qualify(copied / summary.name)
    assert qualify(summary)[0] == 'runtime'


@pytest.mark.parametrize('change', ['outcome', 'error_code', 'structure'])
def test_summary_cannot_override_native_terminal_result(tmp_path, change):
    summary, rows, _ = make_window(tmp_path)
    path = tmp_path / rows[2]['episode_relative']
    record = json.loads(path.read_bytes())
    if change == 'structure':
        record['final_state'] = None
    else:
        record['final_state'][change] = '1' if change == 'outcome' else True
    path.write_text(json.dumps(record))
    rows[2]['episode_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_rows(summary, rows)
    with pytest.raises(ValueError, match='native'):
        qualify(summary)


@pytest.mark.parametrize('version', [None, True, '1', 2])
def test_unknown_native_schema_cannot_qualify(tmp_path, version):
    summary, rows, _ = make_window(tmp_path)
    path = tmp_path / rows[2]['episode_relative']
    record = json.loads(path.read_bytes())
    record['EpisodeSchemaVersion'] = version
    path.write_text(json.dumps(record))
    rows[2]['episode_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_rows(summary, rows)
    with pytest.raises(ValueError, match='schema'):
        qualify(summary)


def test_hybrid_may_escalate_every_real_fast_proposal(tmp_path):
    summary, rows, _ = make_window(tmp_path, policy='hybrid')
    assert all(row['routing_audit']['fast_selected'] == 0 for row in rows)
    assert all(row['routing_audit']['fast_calls'] == 1 for row in rows)
    assert qualify(summary, policy='hybrid', deployment=DEPLOYMENT)[0] == 'runtime'
    deployment = deepcopy(DEPLOYMENT)
    deployment['active_backends']['fast']['calibration_sha256'] = 'different-calibration'
    with pytest.raises(ValueError, match='deployment'):
        qualify(summary, policy='hybrid', deployment=deployment)


def test_hybrid_saved_audit_cannot_replace_native_routing_evidence(tmp_path):
    summary, rows, _ = make_window(tmp_path, policy='hybrid')
    rows[2]['routing_audit']['fast_tokens'] = 999
    write_rows(summary, rows)
    with pytest.raises(ValueError, match='native hybrid'):
        qualify(summary, policy='hybrid', deployment=DEPLOYMENT)


@pytest.mark.parametrize('policy', ['jev', 'llm'])
@pytest.mark.parametrize('value', [0, True, '1', float('nan')])
def test_model_counter_must_be_a_positive_integer(tmp_path, policy, value):
    summary, rows, _ = make_window(tmp_path, policy=policy)
    rows[2]['model_decisions'] = value
    write_rows(summary, rows)
    with pytest.raises(ValueError, match='model decisions'):
        qualify(summary, policy=policy)


def test_legacy_pooled_file_is_rejected_before_any_ros_dispatch(tmp_path, monkeypatch):
    runner = runner_module()
    summary = tmp_path / 'pooled.jsonl'
    rows = [dict(scenario='S1', protocol_sha256=DIGEST, runtime_fingerprint='runtime',
                 policy='fsm', stage='smoke', scenario_exercised=True, harness_error=None,
                 outcome='FAILED' if i < 2 else 'SUCCEEDED', expected='SUCCEEDED',
                 replay_ok=True) for i in range(10)]
    write_rows(summary, rows)
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'fsm', '--stage', 'baseline',
                                     '--batch', 'S1:20', '--smoke-summary', str(summary)])
    monkeypatch.setattr(runner, 'run_episode', lambda *a, **k: pytest.fail('ROS dispatched'))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2


def test_repeated_scenario_cannot_bypass_the_smoke_cap(monkeypatch):
    runner = runner_module()
    monkeypatch.setattr(sys, 'argv', ['runner', '--batch', 'S1:3', 'S1:3'])
    monkeypatch.setattr(runner, 'run_episode', lambda *a, **k: pytest.fail('ROS dispatched'))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2


def test_complete_window_reaches_baseline_dispatch(tmp_path, monkeypatch):
    summary, _, _ = make_window(tmp_path / 'qualifying')
    runner = runner_module()
    monkeypatch.setattr(runner, 'EPISODE_DIR', str(tmp_path / 'new-baseline'))
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'fsm', '--stage', 'baseline',
                                     '--batch', 'S1:1', '--smoke-summary', str(summary)])

    class DispatchReached(Exception):
        pass

    def stop_before_transport(*args, **kwargs):
        raise DispatchReached

    monkeypatch.setattr(runner, 'run_episode', stop_before_transport)
    with pytest.raises(DispatchReached):
        runner.main()


def test_runner_freezes_plan_before_first_reset_and_emits_qualifiable_rows(tmp_path, monkeypatch):
    runner = runner_module()
    monkeypatch.setattr(runner, 'EPISODE_DIR', str(tmp_path))
    monkeypatch.setattr(sys, 'argv', ['runner', '--policy', 'fsm', '--batch', 'S1:5'])
    monkeypatch.setattr(runner, 'replay_episode', lambda *a: [dict(ok=True)])
    monkeypatch.setattr(runner, 'check_scenario_execution', lambda *a: (True, 'synthetic fixture'))
    calls = []

    def simulate_episode(client, spec, ws, seed):
        plans = list((tmp_path / 'batch_plans').glob('*.json'))
        assert len(plans) == 1
        plan = json.loads(plans[0].read_bytes())
        assert len(plan['schedule']) == 5 and plan['schedule'][len(calls)]['seed'] == seed
        summary = tmp_path / (plan['batch_id'] + '.jsonl')
        assert len(summary.read_text().splitlines()) == len(calls)
        evidence = 'synthetic-%d' % len(calls)
        record = dict(EpisodeSchemaVersion=1, final_state=dict(evidence_id=evidence, outcome='0', error_code=0), runtime_fingerprint='runtime',
                      benchmark_protocol=dict(sha256=DIGEST), policy=dict(name='fsm'), steps=[])
        (tmp_path / (evidence + '.json')).write_text(json.dumps(record))
        calls.append(seed)
        return 0, 'RESULT ' + json.dumps(dict(evidence_id=evidence, outcome='OUTCOME_SUCCEEDED')), {}

    monkeypatch.setattr(runner, 'run_episode', simulate_episode)
    assert runner.main() == 0
    summary = next(tmp_path.glob('*.jsonl'))
    assert qualify(summary)[0] == 'runtime' and len(calls) == 5


@pytest.mark.parametrize('with_plan', [True, False])
def test_existing_snapshot_tool_preserves_window_or_keeps_legacy_unqualified(tmp_path, monkeypatch, with_plan):
    original = tmp_path / 'original'
    summary, rows, plan = make_window(original)
    if not with_plan:
        (original / 'batch_plans' / (summary.stem + '.json')).unlink()
    repo = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location('snapshot_window_test', repo / 'setup/105_snapshot_smoke.py')
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    deployment = tmp_path / 'deployment.json'
    deployment.write_text('{}')
    log = tmp_path / 'runner.log'
    log.write_text('SYNTHETIC TEST ONLY\n')
    out = tmp_path / 'snapshot'
    monkeypatch.setattr(sys, 'argv', ['snapshot', '--batch', str(summary), '--out', str(out),
                                    '--deployment', str(deployment), '--runner-log', str(log)])
    snapshot.main()
    manifest = json.loads((out / 'manifest.json').read_bytes())
    assert (out / 'batch_original.jsonl').read_bytes() == summary.read_bytes()
    presentation = tmp_path / 'presentation-copy'
    monkeypatch.setattr(sys, 'argv', ['snapshot', '--batch', str(out / 'batch_portable.jsonl'),
                                    '--out', str(presentation), '--deployment', str(deployment),
                                    '--runner-log', str(log)])
    snapshot.main()
    assert json.loads((presentation / 'manifest.json').read_bytes())['qualification_window'] is None
    if not with_plan:
        assert manifest['qualification_window'] is None
        assert not (out / 'qualification_window').exists()
        return
    frozen = out / manifest['qualification_window']
    assert frozen.read_bytes() == summary.read_bytes()
    assert json.loads((frozen.parent / 'batch_plans' / (summary.stem + '.json')).read_bytes()) == plan
    for row in rows:
        assert (frozen.parent / row['episode_relative']).read_bytes() == (original / row['episode_relative']).read_bytes()
    # A snapshot can itself be snapshotted, with the original host unavailable.
    shutil.rmtree(original)
    second = tmp_path / 'second-snapshot'
    monkeypatch.setattr(sys, 'argv', ['snapshot', '--batch', str(frozen), '--out', str(second),
                                    '--deployment', str(deployment), '--runner-log', str(log)])
    snapshot.main()
    moved = tmp_path / 'moved'
    shutil.move(str(second), moved)
    assert qualify(moved / 'qualification_window' / summary.name)[0] == 'runtime'
