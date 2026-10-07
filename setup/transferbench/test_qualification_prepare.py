import hashlib
import json

import pytest

import qualification_prepare as q


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(q.encoded(value))


@pytest.fixture
def fixture(tmp_path):
    workspace = tmp_path / 'workspace'
    for rel in q.TOOL_FILES:
        p = workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('frozen source\n')
    prompt = 'src/flexcell/flexcell_skills/flexcell_skills/jev_backends.py'
    config = 'src/flexcell/flexcell_skills/config/week1.yaml'
    for rel in (prompt, config):
        p = workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('identity fixture\n')
    calibration = {'schema_version': 1, 'label_definition': 'FSM_ACTION_AGREEMENT',
                   'model': 'clef-flash-q8_0', 'model_sha256': 'a'*64,
                   'prompt_sha256': q.sha(workspace / prompt),
                   'bins': [{'n': 100, 'wilson_lower': .9}]}
    dump(tmp_path / 'calibration.json', calibration)
    profile = {'policy': 'hybrid', 'threshold': .85, 'source_sha256': {prompt: calibration['prompt_sha256']},
               'harness_sha256': {}, 'interface_sources_sha256': {}, 'params_sha256': q.sha(workspace / config),
               'active_backends': {'fast': {'endpoint': 'http://example.invalid:11435/v1/systemone',
                                          'model': calibration['model'], 'model_sha256': calibration['model_sha256'],
                                          'calibration_sha256': q.sha(tmp_path / 'calibration.json')}}}
    deployment = dict(profile, runtime_fingerprint=hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest())
    dump(tmp_path / 'deployment.json', deployment)
    world = {'world_state': {'objects': [{'name': n, 'pose': {'position': dict(zip(('x','y','z'), p))}}
                                         for n, p in q.SOURCE.items()]}}
    dump(tmp_path / 'history/old.json', {'initial_world_state': world, 'steps': []})
    dump(tmp_path / 'reference.json', {'adaptation': {'seed1': q.SOURCE, 'seed2': q.SOURCE}})
    dump(tmp_path / 'budget.json', {'currency': 'CNY', 'limit_microyuan': 5000000,
                                  'calls': [{'id': 'old-call', 'reserved_microyuan': 1000}]})
    return {'seed': 2026100701, 'history_root': tmp_path / 'history',
            'deployment_path': tmp_path / 'deployment.json', 'calibration_path': tmp_path / 'calibration.json',
            'reference_path': tmp_path / 'reference.json', 'budget_path': tmp_path / 'budget.json',
            'revision': 'b'*40, 'workspace': workspace}


def prepared(tmp_path, fixture):
    root = tmp_path / 'prepared'
    result = q.prepare(root, **fixture)
    return root, result


def reseal(root, rel, value):
    dump(root / rel, value)
    manifest = q.loads((root / 'SHA256SUMS.json').read_bytes())
    manifest[rel] = {'sha256': q.sha(root / rel), 'bytes': (root / rel).stat().st_size}
    dump(root / 'SHA256SUMS.json', manifest)
    return q.sha(root / 'SHA256SUMS.json')


def test_prepare_is_reproducible_frozen_and_contains_no_results(tmp_path, fixture):
    root, result = prepared(tmp_path, fixture)
    other = tmp_path / 'again'
    again = q.prepare(other, **fixture)
    assert result == again
    assert result['target_cases'] == 200 and result['schedule_slots'] == 450
    assert result['native_episodes_executed'] == result['model_calls'] == 0
    assert (root / 'calibration.json').read_bytes() == fixture['calibration_path'].read_bytes()
    report = q.verify(root, result['package_sha256'], workspace=fixture['workspace'], history_root=fixture['history_root'])
    assert report['implementation_verified'] and report['history_verified']
    assert not report['sampling_authorized'] and not report['ready_for_large_test']
    protocol = q.loads((root / 'protocol.json').read_bytes())
    assert protocol['custody'].startswith('NOT_INDEPENDENT') and protocol['AC90'] == 'NOT_RUN'
    assert not any(p.name in ('results.json', 'cost.jsonl', 'episodes') for p in root.iterdir())


def test_pairing_units_and_source_regression_schedule(tmp_path, fixture):
    root, _ = prepared(tmp_path, fixture)
    schedule = q.loads((root / 'schedule.json').read_bytes())
    for axis in ('T1','T3'):
        targets = [r for r in schedule if r['axis'] == axis and r['purpose'] == 'target']
        assert len(targets) == 200
        assert sum(r['native_episodes'] for r in targets) == (200 if axis == 'T1' else 600)
        assert [r['arm'] for r in targets[:4]] == ['fsm','hybrid','hybrid','fsm']
        for i in range(0, len(targets), 2):
            assert targets[i]['case_id'] == targets[i+1]['case_id']
        for i in range(0, len(targets), 40):
            assert sum(r['arm'] == 'fsm' for r in targets[i:i+40:2]) == 10
    regression = [r for r in schedule if r['purpose'] == 'source_regression']
    assert len(regression) == 50
    assert len([r for r in regression if r['axis'] == 'T1']) == 10
    assert sum(r['native_episodes'] for r in regression) == 50


def test_candidates_exclude_recorded_states_and_each_other(tmp_path, fixture):
    initial = q.history_snapshot(fixture['history_root'])
    first = q.cases(fixture['seed'], initial)
    initial['layouts'].append(first[0]['initial_objects'])
    changed = q.cases(fixture['seed'], initial)
    assert changed[0]['candidate_index'] > first[0]['candidate_index']
    for i, item in enumerate(changed):
        assert not any(q.near(item['initial_objects'], old) for old in initial['layouts'])
        assert not any(q.near(item['initial_objects'], old['initial_objects']) for old in changed[:i])
        if item['axis'] == 'T3':
            q.prepare_plan(item['request']['plan'])


def test_existing_preparation_is_never_replaced(tmp_path, fixture):
    root, result = prepared(tmp_path, fixture)
    with pytest.raises(ValueError, match='already exists'):
        q.prepare(root, **fixture)
    assert q.sha(root / 'SHA256SUMS.json') == result['package_sha256']


@pytest.mark.parametrize('raw', ['{"steps":[],"steps":[]}', '{"steps":[],"x":NaN}', '{"steps":[],"x":1e999}'])
def test_invalid_history_is_rejected_without_output(tmp_path, fixture, raw):
    (fixture['history_root'] / 'invalid.json').write_text(raw)
    with pytest.raises(ValueError):
        q.prepare(tmp_path / 'output', **fixture)
    assert not (tmp_path / 'output').exists()


def test_history_drift_refuses_to_reuse_the_frozen_package(tmp_path, fixture):
    root, result = prepared(tmp_path, fixture)
    (fixture['history_root'] / 'new.json').write_bytes((fixture['history_root'] / 'old.json').read_bytes())
    with pytest.raises(ValueError, match='history drift'):
        q.verify(root, result['package_sha256'], history_root=fixture['history_root'])


def test_source_drift_refuses_qualification_identity(tmp_path, fixture):
    root, result = prepared(tmp_path, fixture)
    (fixture['workspace'] / q.TOOL_FILES[0]).write_text('new code\n')
    with pytest.raises(ValueError, match='implementation drift'):
        q.verify(root, result['package_sha256'], workspace=fixture['workspace'])


def test_bytes_and_resealed_schedule_tampering_are_rejected(tmp_path, fixture):
    root, result = prepared(tmp_path, fixture)
    value = q.loads((root / 'schedule.json').read_bytes())
    value[0]['arm'] = 'hybrid'
    changed_sha = reseal(root, 'schedule.json', value)
    with pytest.raises(ValueError, match='expected digest'):
        q.verify(root, result['package_sha256'])
    with pytest.raises(ValueError, match='semantic mismatch'):
        q.verify(root, changed_sha)


@pytest.mark.parametrize('field,value', [('sampling_authorized', True), ('native_episodes_executed', False),
                                       ('n_per_cell', 99), ('AC90', 'PASS')])
def test_resealed_gate_or_coercive_result_is_rejected(tmp_path, fixture, field, value):
    root, _ = prepared(tmp_path, fixture)
    protocol = q.loads((root / 'protocol.json').read_bytes()); protocol[field] = value
    with pytest.raises(ValueError, match='semantic mismatch'):
        q.verify(root, reseal(root, 'protocol.json', protocol))


@pytest.mark.parametrize('kind', ['extra', 'symlink', 'escape'])
def test_package_membership_and_path_escape_rejected(tmp_path, fixture, kind):
    root, result = prepared(tmp_path, fixture)
    if kind == 'extra':
        (root / 'unexpected.json').write_text('{}')
    elif kind == 'symlink':
        saved = tmp_path / 'outside.json'; saved.write_bytes((root / 'cases.json').read_bytes())
        (root / 'cases.json').unlink(); (root / 'cases.json').symlink_to(saved)
    else:
        manifest = q.loads((root / 'SHA256SUMS.json').read_bytes())
        manifest['../outside.json'] = manifest.pop('cases.json')
        dump(root / 'SHA256SUMS.json', manifest); result['package_sha256'] = q.sha(root / 'SHA256SUMS.json')
    with pytest.raises(ValueError):
        q.verify(root, result['package_sha256'])


@pytest.mark.parametrize('change', ['identity', 'bool_count', 'closed_gate'])
def test_bad_calibration_is_rejected(tmp_path, fixture, change):
    calibration = q.loads(fixture['calibration_path'].read_bytes())
    if change == 'identity': calibration['prompt_sha256'] = 'f'*64
    elif change == 'bool_count': calibration['bins'][0]['n'] = True
    else: calibration['bins'][0]['wilson_lower'] = .84
    dump(fixture['calibration_path'], calibration)
    deployment = q.loads(fixture['deployment_path'].read_bytes())
    deployment['active_backends']['fast']['calibration_sha256'] = q.sha(fixture['calibration_path'])
    profile = {k:v for k,v in deployment.items() if k != 'runtime_fingerprint'}
    deployment['runtime_fingerprint'] = hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest()
    dump(fixture['deployment_path'], deployment)
    with pytest.raises(ValueError, match='calibration'):
        q.prepare(tmp_path / 'bad', **fixture)


@pytest.mark.parametrize('cost', [True, -1, 1001])
def test_budget_cost_cannot_be_coerced_or_reset(tmp_path, fixture, cost):
    budget = q.loads(fixture['budget_path'].read_bytes()); budget['calls'][0]['settled_microyuan'] = cost
    dump(fixture['budget_path'], budget)
    with pytest.raises(ValueError, match='budget cost'):
        q.prepare(tmp_path / 'bad', **fixture)


def test_nondefault_cap_is_rejected(tmp_path, fixture):
    budget = q.loads(fixture['budget_path'].read_bytes()); budget['limit_microyuan'] = 10000000
    dump(fixture['budget_path'], budget)
    with pytest.raises(ValueError, match='persistent CNY5'):
        q.prepare(tmp_path / 'bad', **fixture)


def test_additional_runtime_source_cannot_be_ignored(tmp_path, fixture):
    root = fixture['workspace'] / 'src/flexcell/flexcell_skills/flexcell_skills'
    (root / 'new_policy.py').write_text('added implementation\n')
    with pytest.raises(ValueError, match='file-set drift'):
        q.prepare(tmp_path / 'bad', **fixture)


@pytest.mark.parametrize('change', ['extra_secret', 'url_credential', 'bool_digest'])
def test_secret_or_invalid_fast_identity_is_rejected_before_output(tmp_path, fixture, change):
    deployment = q.loads(fixture['deployment_path'].read_bytes())
    fast = deployment['active_backends']['fast']
    if change == 'extra_secret': fast['api_key'] = 'SYNTHETIC_SECRET'
    elif change == 'url_credential': fast['endpoint'] = 'http://user:password@example.invalid/path'
    else: fast['model_sha256'] = True
    profile = {k:v for k,v in deployment.items() if k != 'runtime_fingerprint'}
    deployment['runtime_fingerprint'] = hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest()
    dump(fixture['deployment_path'], deployment)
    with pytest.raises(ValueError):
        q.prepare(tmp_path / 'bad', **fixture)
    assert not (tmp_path / 'bad').exists()
