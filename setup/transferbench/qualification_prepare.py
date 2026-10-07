"""Offline, deterministic qualification inputs. There is deliberately no runner."""

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.composite import prepare_plan
from flexcell_skills.contracts.receipt_json import loads, same_typed

OBJECTS = ('target_box_a', 'target_box_b')
SOURCE = dict(zip(OBJECTS, ([.22, 0., .0175], [.20, -.18, .0175])))
ZONES = dict(zip(OBJECTS, ([.12, -.15, .0175], [.25, .05, .0175])))
N = 100
TOOL_FILES = ('setup/132_qualification_prepare.py',
              'setup/transferbench/qualification_prepare.py',
              'setup/transferbench/t1_pilot.py', 'setup/127_composite_audit.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def digest(value):
    return sha_bytes(encoded(value))


def sha_value(value, length=64):
    require(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value),
            'invalid digest')


def regular(root, rel):
    require(type(rel) is str and rel == str(PurePosixPath(rel))
            and not PurePosixPath(rel).is_absolute()
            and '..' not in PurePosixPath(rel).parts and '\\' not in rel,
            'unsafe relative path')
    p = root / rel
    require(not any(q.is_symlink() for q in (p, *p.parents) if q != root.parent)
            and p.is_file() and p.resolve().is_relative_to(root.resolve()),
            'regular contained file required: ' + rel)
    return p


def point(value):
    return (type(value) is list and len(value) == 3 and
            all(type(v) in (int, float) and math.isfinite(v) for v in value))


def layout(value):
    require(type(value) is dict and set(value) == set(OBJECTS)
            and all(point(value[n]) for n in OBJECTS), 'invalid two-object layout')
    return value


def near(left, right):
    return all(math.dist(left[n], right[n]) <= .001 for n in OBJECTS)


def recorded_layouts(episode):
    require(type(episode) is dict and type(episode.get('steps')) is list,
            'history episode or steps unavailable')
    states = [episode.get('initial_world_state')]
    for step in episode['steps']:
        require(type(step) is dict, 'invalid history step')
        policy = step.get('policy_input')
        require(type(policy) is dict, 'invalid history policy input')
        states.append(policy.get('world_state_canonical'))
    found = []
    for raw in states:
        if raw is None:
            continue
        world = loads(raw) if type(raw) is str else raw
        require(type(world) is dict, 'invalid history world state')
        objects = world.get('world_state', world).get('objects')
        require(type(objects) is list, 'unrecognized history object representation')
        positions = {}
        for obj in objects:
            require(type(obj) is dict and type(obj.get('name')) is str,
                    'invalid history object')
            name = obj['name']
            require(name not in positions, 'duplicate history object')
            p = obj.get('pose', {}).get('position')
            require(type(p) is dict and set(p) == {'x', 'y', 'z'},
                    'invalid history position')
            positions[name] = [p[k] for k in ('x', 'y', 'z')]
            require(point(positions[name]), 'nonfinite history position')
        if set(OBJECTS).issubset(positions):
            found.append({name: positions[name] for name in OBJECTS})
    return found


def history_snapshot(root):
    files, unique, count = {}, {}, 0
    paths = sorted(root.glob('*.json'))
    require(bool(paths), 'nonempty available episode history required')
    for p in paths:
        p = regular(root, p.name)
        raw = p.read_bytes()
        states = recorded_layouts(loads(raw))
        files[p.name] = {'sha256': sha_bytes(raw), 'bytes': len(raw)}
        count += len(states)
        for state in states:
            unique.setdefault(digest(state), state)
    require(bool(unique), 'no comparable two-object history')
    return {'files': files, 'observed_states': count,
            'layouts': [unique[k] for k in sorted(unique)],
            'coverage': 'available recorded two-object states only; unrecorded exposure UNKNOWN'}


def number(seed, axis, attempt, coordinate):
    raw = hashlib.sha256(('%d:%s:%d:%d' % (seed, axis, attempt, coordinate)).encode()).digest()
    return int.from_bytes(raw[:8], 'big') / (2**64 - 1)


def cases(seed, history):
    require(type(seed) is int and 0 <= seed < 2**63, 'seed must be nonnegative integer')
    old = [layout(item) for item in history['layouts']]
    result, chosen = [], []
    for axis in ('T1', 'T3'):
        attempt, accepted = 0, 0
        while accepted < N:
            require(attempt < 10000, 'candidate generation exhausted; do not silently change seed')
            initial = {name: [round(SOURCE[name][i] + (number(seed, axis, attempt, 2*j+i)*2-1)*.025, 4)
                              for i in range(2)] + [.0175] for j, name in enumerate(OBJECTS)}
            attempt += 1
            if (math.dist(*initial.values()) < .12
                    or any(math.dist(p, z) < .05 for p in initial.values() for z in ZONES.values())
                    or any(near(initial, previous) for previous in old + chosen)):
                continue
            case_id = '%s-%03d' % (axis, accepted + 1)
            request = {'action': 'demo', 'scenario_id': 'qualification_' + case_id}
            if axis == 'T3':
                plan = {'scenario_id': 'qualification_' + case_id, 'initial_objects': initial,
                        'stages': [{'stage_id': 'buffer-B', 'object_name': OBJECTS[1], 'destination': ZONES[OBJECTS[0]]},
                                   {'stage_id': 'relocate-A', 'object_name': OBJECTS[0], 'destination': initial[OBJECTS[1]]},
                                   {'stage_id': 'return-B', 'object_name': OBJECTS[1], 'destination': initial[OBJECTS[0]]}],
                        'final_empty_positions': [ZONES[OBJECTS[0]]], 'position_tolerance_m': .06,
                        'clearance_m': .05, 'motion_profile_id': 'demo_slow'}
                request = {'action': 'composite', 'plan': prepare_plan(plan)}
            result.append({'case_id': case_id, 'axis': axis, 'candidate_index': attempt - 1,
                           'initial_objects': initial, 'request': request,
                           'native_episodes_per_task': 1 if axis == 'T1' else 3})
            chosen.append(initial)
            accepted += 1
    return result


def regressions(reference):
    initial = reference.get('adaptation')
    require(type(initial) is dict and len(initial) == 2, 'two frozen familiar T1 layouts required')
    familiar = [('S1', SOURCE), ('T1-familiar-01', layout(initial[sorted(initial)[0]])),
                ('T1-familiar-02', layout(initial[sorted(initial)[1]])), ('T1-canonical', SOURCE)]
    return [{'case_id': name, 'initial_objects': pos,
             'request': {'action': 'demo', 'scenario_id': 'week1_demo_v1' if name == 'S1' else name},
             'native_episodes_per_task': 1} for name, pos in familiar]


def schedule(items):
    rows = []
    for axis in ('T1', 'T3'):
        for index, case in enumerate(item for item in items if item['axis'] == axis):
            arms = ('fsm', 'hybrid') if index % 2 == 0 else ('hybrid', 'fsm')
            for arm in arms:
                rows.append({'slot': len(rows), 'axis': axis, 'arm': arm, 'purpose': 'target',
                             'pair_id': case['case_id'], 'case_id': case['case_id'],
                             'native_episodes': case['native_episodes_per_task']})
            if (index+1) % 20 == 0:
                for case_id in (('S1',) if axis == 'T1' else
                                ('S1', 'T1-familiar-01', 'T1-familiar-02', 'T1-canonical')):
                    for arm in arms[::-1]:
                        rows.append({'slot': len(rows), 'axis': axis, 'arm': arm,
                                     'purpose': 'source_regression',
                                     'pair_id': '%s-after-%03d-%s' % (axis, index+1, case_id),
                                     'case_id': case_id, 'native_episodes': 1})
    return rows


def validate_model(fast, calibration, pins):
    require(type(fast) is dict and set(fast) == {'endpoint', 'model', 'model_sha256', 'calibration_sha256'},
            'unexpected fast identity fields; no credentials in preparation')
    sha_value(fast['model_sha256']); sha_value(fast['calibration_sha256'])
    endpoint = urlsplit(fast['endpoint'])
    require(endpoint.scheme in ('http', 'https') and bool(endpoint.hostname)
            and not endpoint.username and not endpoint.password and not endpoint.query and not endpoint.fragment,
            'plain inference endpoint required; no credential-bearing URL')
    require(fast['model'] == 'clef-flash-q8_0', 'clef Q8 identity required')
    require(type(calibration['schema_version']) is int and calibration['schema_version'] == 1
            and calibration['label_definition'] == 'FSM_ACTION_AGREEMENT'
            and calibration['model'] == fast['model'] and calibration['model_sha256'] == fast['model_sha256']
            and calibration['prompt_sha256'] == pins['src/flexcell/flexcell_skills/flexcell_skills/jev_backends.py'],
            'calibration identity mismatch')
    eligible = any(type(b['n']) is int and b['n'] >= 5
                   and type(b['wilson_lower']) in (int, float) and .85 <= b['wilson_lower'] <= 1
                   for b in calibration['bins'])
    require(eligible, 'calibration gate closed')


def identities(deployment, revision, workspace, calibration):
    sha_value(revision, 40)
    require(deployment['policy'] == 'hybrid' and type(deployment['threshold']) is float
            and deployment['threshold'] == .85, 'hybrid 0.85 baseline required')
    profile = {k: v for k, v in deployment.items() if k not in ('head', 'install', 'runtime_fingerprint')}
    runtime_sha = lambda p: sha_bytes(json.dumps(p, sort_keys=True, allow_nan=False).encode())
    require(runtime_sha(profile) == deployment['runtime_fingerprint'], 'deployment digest mismatch')
    pins = {}
    for key in ('source_sha256', 'harness_sha256', 'interface_sources_sha256'):
        pins.update(deployment[key])
    package = workspace / 'src/flexcell/flexcell_skills/flexcell_skills'
    require({str(p.relative_to(workspace)) for p in package.rglob('*.py')}
            == set(deployment['source_sha256']), 'runtime source file-set drift')
    pins.update({rel: sha(regular(workspace, rel)) for rel in TOOL_FILES})
    pins['src/flexcell/flexcell_skills/config/week1.yaml'] = deployment['params_sha256']
    for rel, expected in pins.items():
        sha_value(expected)
        require(sha(regular(workspace, rel)) == expected, 'implementation drift: ' + rel)
    fast = deployment['active_backends']['fast']
    validate_model(fast, calibration, pins)
    return {'implementation_revision': revision, 'source_sha256': pins,
            'model_identity': fast,
            'runtime_configuration': {k: deployment.get(k) for k in
                ('params_sha256', 'world_sha256', 'dds_profile_sha256', 'ros_domain_id',
                 'rmw_implementation', 'threshold', 'policy_timeouts_s', 'startup_health_timeout_s')},
            'proposed_runtime_fingerprints': {arm: runtime_sha(dict(profile, policy=arm))
                                              for arm in ('fsm', 'hybrid')},
            'fsm_fingerprint_status': 'DERIVED_EXPECTATION; no FSM deployment executed by preparation',
            'slow_exact_weights': 'UNKNOWN'}


def budget_snapshot(raw):
    state = loads(raw)
    require(type(state.get('limit_microyuan')) is int and state['limit_microyuan'] == 5000000
            and state.get('currency') == 'CNY' and type(state.get('calls')) is list,
            'existing persistent CNY5 budget required; never reset')
    committed, ids = 0, set()
    for call in state['calls']:
        require(type(call) is dict and type(call.get('id')) is str and call['id'] not in ids,
                'invalid or duplicate budget call')
        ids.add(call['id'])
        reserve = call['reserved_microyuan']; cost = call.get('settled_microyuan', reserve)
        require(type(reserve) is int and type(cost) is int and 0 <= cost <= reserve,
                'invalid budget cost')
        committed += cost
    require(committed < 5000000, 'existing budget exhausted')
    return {'source_sha256': sha_bytes(raw), 'existing_call_ids': sorted(ids),
            'existing_committed_upper_microyuan': committed, 'absolute_cap_microyuan': 5000000,
            'additional_cumulative_stop_microyuan': 250000, 'budget_reset': False,
            'envelope_status': 'NOT_RATIFIED', 'actual_invoice_and_gpu_cost': 'UNKNOWN'}


def package_payload(seed, history, reference, identity, calibration, budget):
    items = cases(seed, history)
    predicate = {'T1': 'typed task/client outcome 0; matching run/goal UUID; both native measured zone errors <=0.06m; PICK/PLACE/VERIFY per object',
                 'T3': 'three native stage successes and fresh joint swapped positions; buffer empty; components are not independent samples',
                 'signals': 'reject all signals including -6/134 even after earlier ok:true',
                 'unknown_or_quarantine': 'stop; preserve partial matrix; no replacement sampling',
                 'source_regression_failure': 'stop phase; preserve every registered slot'}
    return {'identity.json': identity, 'history.json': history, 'calibration.json': calibration,
            'familiar_inputs.json': reference, 'budget.json': budget, 'cases.json': items,
            'regressions.json': regressions(reference), 'schedule.json': schedule(items),
            'protocol.json': {'schema_version': 1, 'record_kind': 'QUALIFICATION_INPUT_PREPARATION',
                'protocol_id': 'transferbench-qualification-v2-candidate', 'status': 'PREPARED_NOT_RATIFIED',
                'seed': seed, 'n_per_cell': N, 'axes': ['T1', 'T3'], 'arms': ['fsm', 'hybrid'],
                'target_logical_tasks': 400, 'target_native_episodes': 800, 'regression_native_episodes': 50,
                'sampling_authorized': False, 'ready_for_large_test': False, 'large_tests_started': False,
                'native_episodes_executed': 0, 'model_calls': 0, 'n_ge_50': 'FROZEN', 'AC90': 'NOT_RUN',
                'custody': 'NOT_INDEPENDENT; candidate inputs disclosed in repository; no blind holdout claim',
                'geometry': 'SHA256 stream, +/-25mm around canonical positions; >=120mm separation and >=50mm from zones; 1mm two-object historical exclusion',
                'reachability': 'NOT_EVALUATED; static geometry is not IK or physical acceptance',
                'composition_scope': 'frozen three-stage swap under layouts; not unseen composition generalization',
                'statistical_assumptions': 'NOT_RATIFIED; fixed-four-cell proposal remains separate',
                'success_predicates': predicate, 'remaining_gates': ['independent custody and protocol ratification',
                    'NET-001 stability NOT_ACCEPTED', 'GRASP-B-001 root UNKNOWN', 'budget envelope NOT_RATIFIED',
                    'qualification ledger/runner NOT_IMPLEMENTED']}}


def prepare(root, *, seed, history_root, deployment_path, calibration_path,
            reference_path, budget_path, revision, workspace):
    require(not root.exists(), 'output already exists; preserve original preparation')
    deployment_raw = deployment_path.read_bytes()
    deployment = loads(deployment_raw); calibration_raw = calibration_path.read_bytes()
    calibration = loads(calibration_raw)
    require(sha_bytes(calibration_raw) == deployment['active_backends']['fast']['calibration_sha256'],
            'calibration file hash mismatch')
    identity = identities(deployment, revision, workspace, calibration)
    identity['baseline_deployment_sha256'] = sha_bytes(deployment_raw)
    history = history_snapshot(history_root)
    payload = package_payload(seed, history, loads(reference_path.read_bytes()), identity,
                              calibration, budget_snapshot(budget_path.read_bytes()))
    root.mkdir(parents=True, exist_ok=False)
    for rel, value in payload.items():
        with (root / rel).open('xb') as stream:
            stream.write(calibration_raw if rel == 'calibration.json' else encoded(value))
    seal = {rel: {'bytes': (root / rel).stat().st_size, 'sha256': sha(root / rel)} for rel in sorted(payload)}
    with (root / 'SHA256SUMS.json').open('xb') as stream:
        stream.write(encoded(seal))
    return {'ok': True, 'status': 'PREPARED_NOT_RATIFIED', 'package_sha256': sha(root / 'SHA256SUMS.json'),
            'target_cases': len(payload['cases.json']), 'schedule_slots': len(payload['schedule.json']),
            'history_files': len(history['files']), 'model_calls': 0, 'native_episodes_executed': 0,
            'sampling_authorized': False, 'ready_for_large_test': False}


def verify(root, expected_sha, *, workspace=None, history_root=None):
    sha_value(expected_sha)
    require(not root.is_symlink(), 'package root must not be symlink')
    require(sha(regular(root, 'SHA256SUMS.json')) == expected_sha, 'package seal differs from expected digest')
    manifest = loads((root / 'SHA256SUMS.json').read_bytes())
    require(type(manifest) is dict and set(manifest) == {'identity.json', 'history.json', 'calibration.json',
            'familiar_inputs.json', 'budget.json', 'cases.json', 'regressions.json', 'schedule.json', 'protocol.json'},
            'package file set invalid')
    require({p.name for p in root.iterdir()} == set(manifest) | {'SHA256SUMS.json'}, 'unexpected package content')
    data = {}
    for rel, pin in manifest.items():
        p = regular(root, rel)
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int
                and pin['bytes'] == p.stat().st_size and pin['sha256'] == sha(p), 'package file changed: ' + rel)
        data[rel] = loads(p.read_bytes())
    identity = data['identity.json']
    sha_value(identity['implementation_revision'], 40)
    require(manifest['calibration.json']['sha256'] == identity['model_identity']['calibration_sha256'],
            'calibration byte identity mismatch')
    validate_model(identity['model_identity'], data['calibration.json'], identity['source_sha256'])
    protocol = data['protocol.json']
    expected = package_payload(protocol['seed'], data['history.json'], data['familiar_inputs.json'],
                               data['identity.json'], data['calibration.json'], data['budget.json'])
    require(same_typed(data, expected), 'package semantic mismatch; reject re-sealed changed schedule or gate')
    if workspace is not None:
        for rel, digest_value in data['identity.json']['source_sha256'].items():
            require(sha(regular(workspace, rel)) == digest_value, 'implementation drift: ' + rel)
    if history_root is not None:
        require(same_typed(history_snapshot(history_root), data['history.json']), 'history drift; new preparation required')
    return {'ok': True, 'frozen_package_ok': True, 'package_sha256': expected_sha,
            'implementation_verified': workspace is not None, 'history_verified': history_root is not None,
            'target_cases': len(data['cases.json']), 'schedule_slots': len(data['schedule.json']),
            'sampling_authorized': False, 'ready_for_large_test': False,
            'model_calls': 0, 'native_episodes_executed': 0}
