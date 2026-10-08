"""Additional fast-arm gate for the frozen three-slot Hybrid continuation.

Uses the original collector lock, budgets, health gates and claim/commit engine.
The gate is a separately pinned instrument; production and old evidence stay put.
"""
from pathlib import Path

import bounded_runner as runner
import qualification_prepare as q
from flexcell_skills.contracts.routing_audit import audit_routing_episode

TOOL_FILES = ('setup/135_bounded_hybrid_resume.py',
              'setup/transferbench/bounded_hybrid_guard.py')
COUNTERS = ('bootstrap', 'model_decisions', 'fast_selected', 'slow_selected',
            'fsm_fallbacks', 'fast_calls', 'fast_tokens')


def manifest(root, workspace, revision):
    q.sha_value(revision, 40)
    plan, rows, _, committed, _ = runner.read(root, workspace)
    q.require(plan.get('job_order') == 'local-first'
              and [j['arm'] for j in plan['jobs']] == ['fsm'] * 3 + ['hybrid'] * 3,
              'guard requires the frozen local-first collector')
    prefix = next((row for row in rows if row['event'] == 'PAUSED'
                   and type(row['completed_slots']) is int and row['completed_slots'] == 3), None)
    q.require(prefix is not None and len(committed) >= 3,
              'three committed FSM tasks and a paused boundary required')
    q.require(all(row['outcome'] == 'SUCCEEDED' for row in committed[:3]),
              'FSM prefix was not fully successful')
    q.require(sum(len(row['native_episode_ids']) for row in committed[:3]) == 5,
              'FSM prefix must contain exactly five native episodes')
    prefix_rows = rows[:prefix['seq'] + 1]
    q.require([row['slot'] for row in prefix_rows if row['event'] == 'CLAIMED'] == [0, 1, 2],
              'Hybrid already claimed before the registered boundary')
    identity = q.loads(q.regular(root / 'inputs', 'identity.json').read_bytes())
    raw = q.regular(root, 'events.jsonl').read_bytes().splitlines(keepends=True)
    return {'schema_version': 1, 'record_kind': 'REGISTERED_HYBRID_RESUME_GUARD',
            'implementation_revision': revision, 'collector_root': str(root.resolve()),
            'collector_plan_sha256': q.sha(root / 'plan.json'),
            'input_package_sha256': plan['input_package_sha256'],
            'registered_prefix_sha256': q.sha_bytes(b''.join(raw[:prefix['seq'] + 1])),
            'registered_prefix_tail_sha256': prefix['sha256'],
            'guard_source_sha256': {rel: q.sha(q.regular(workspace, rel)) for rel in TOOL_FILES},
            'baseline_completed_slots': 3, 'baseline_native_episodes': 5,
            'remaining_slots': [3, 4, 5], 'remaining_native_episode_cap': 5,
            'runtime_fingerprint': identity['proposed_runtime_fingerprints']['hybrid'],
            'model_identity': identity['model_identity'],
            'threshold': .85, 'collector_budget_path': plan['budget_path'],
            'additional_cumulative_stop_microyuan': 250000, 'budget_reset': False,
            'rule': 'each model-driven episode has real fast proposals and positive measured tokens; each Hybrid task has positive total fast usage',
            'fast_selection_required': False,
            'instrument_scope': 'ADDITIONAL_DEVELOPMENT_GATE; not a new production deployment',
            'pooling_with_unguarded_attempts': 'FORBIDDEN',
            'registration_native_episodes_executed': 0, 'registration_model_calls': 0,
            'qualification_sampling_authorized': False, 'ready_for_large_test': False,
            'n_ge_50': 'FROZEN', 'AC90': 'NOT_RUN'}


def register(path, root, workspace, revision):
    q.require('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
              'guard output cannot use symlinks or parent traversal')
    q.require(not path.exists() and not path.is_symlink(), 'guard output already exists; never replace')
    q.require(not path.resolve().is_relative_to(root.resolve()), 'guard manifest must be outside collector')
    state = runner.status(root, workspace)
    q.require(state['state'] == 'PAUSED' and state['completed_slots'] == 3
              and state['native_episode_count'] == 5 and state['resume_allowed'] is True,
              'register only before the first Hybrid claim')
    value = manifest(root, workspace, revision)
    path.parent.mkdir(parents=True, exist_ok=True)
    runner.write(path, value)
    return {'ok': True, 'guard_sha256': q.sha(path), 'collector_state': state['state'],
            'completed_slots': 3, 'pending_hybrid_slots': 3,
            'dispatch_authorized': False, 'model_calls': 0, 'native_episodes_executed': 0,
            'qualification_sampling_authorized': False, 'ready_for_large_test': False,
            'n_ge_50': 'FROZEN'}


def audit(directory, original, binding):
    """Recompute from raw episodes, not the old passing audit or its counters."""
    result = {'schema_version': 1, 'ok': False, 'errors': [], 'episodes': [],
              'runtime_fingerprint': binding['runtime_fingerprint'],
              'calibration_sha256': binding['model_identity']['calibration_sha256'],
              **{key: 0 for key in COUNTERS}}
    errors = result['errors']
    if original.get('outcome') not in ('SUCCEEDED', 'FAILED'):
        errors.append('original adapter has no confirmed native terminal')
        return result
    try:
        rc = original.get('client_return_code')
        q.require(type(rc) is int and rc in (0, 2), 'failed, signaled or unconfirmed native process')
        q.require(original['outcome'] != 'SUCCEEDED' or rc == 0, 'nonzero process cannot prove success')
        client = q.loads(q.regular(directory, 'client.json').read_bytes())
        q.require(type(client['return_code']) is int and client['return_code'] == rc,
                  'native process receipt differs from original result')
        deployment = q.loads(q.regular(directory, 'deployment.json').read_bytes())
        q.require(deployment['policy'] == 'hybrid' and type(deployment['threshold']) is float
                  and deployment['threshold'] == binding['threshold']
                  and deployment['runtime_fingerprint'] == binding['runtime_fingerprint']
                  and q.same_typed(deployment['active_backends']['fast'], binding['model_identity']),
                  'Hybrid deployment differs from registered guard identity')
        q.require(original['runtime_fingerprint'] == binding['runtime_fingerprint']
                  and original['calibration_sha256'] == result['calibration_sha256'],
                  'original result identity differs from deployment')
        ids, episodes = [], []
        for path in sorted((directory / 'episodes').glob('*.json')):
            episode = q.loads(q.regular(directory / 'episodes', path.name).read_bytes())
            q.require(episode.get('policy', {}).get('name') == 'hybrid', 'episode is not Hybrid')
            q.require(type(episode.get('run_id')) is str and episode['run_id'] not in ids,
                      'duplicate or missing native episode identity')
            ids.append(episode['run_id'])
            report = audit_routing_episode(episode, deployment)
            q.require(report['ok'] is True, 'frozen routing audit failed')
            q.require(all(type(report[k]) is int and report[k] >= 0 for k in COUNTERS),
                      'invalid routing counter')
            if report['model_decisions'] and not report['fast_calls']:
                errors.append(episode['run_id'] + ': no real fast proposal in model-driven episode')
            if report['fast_tokens'] < report['fast_calls'] or report['fsm_fallbacks']:
                errors.append(episode['run_id'] + ': invalid fast usage or non-bootstrap fallback')
            q.require(report['model_decisions'] == report['fast_selected'] + report['slow_selected'],
                      'selection counters disagree')
            episodes.append({'run_id': episode['run_id'], **{k: report[k] for k in COUNTERS}})
            for key in COUNTERS: result[key] += report[key]
        q.require(ids and set(ids) == set(original['native_episode_ids'])
                  and len(ids) == len(original['native_episode_ids']), 'missing or foreign episode evidence')
        result['episodes'] = episodes
        if not result['fast_calls'] or not result['fast_tokens']:
            errors.append('Hybrid task has no real fast calls with measured tokens')
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    result['ok'] = not errors
    return result


def guarded_result(original, gate, guard_sha):
    result = dict(original, resume_guard_sha256=guard_sha, fast_arm_gate_ok=gate['ok'])
    if gate['ok'] is not True:
        # Preserve an existing native failure/unknown. A green adapter result
        # without provenance is a harness error, not physical success evidence.
        if result['outcome'] == 'SUCCEEDED': result['outcome'] = 'HARNESS_ERROR'
        result['stop'] = True
        result['error'] = 'fast-arm gate failed: ' + '; '.join(gate['errors'])
    return result


def verify(path, expected_sha, workspace):
    q.sha_value(expected_sha)
    q.require(q.sha(q.regular(path.parent, path.name)) == expected_sha, 'guard differs from expected digest')
    value = q.loads(path.read_bytes())
    q.require(type(value) is dict and type(value['collector_root']) is str
              and Path(value['collector_root']).is_absolute(), 'absolute collector identity required')
    root = Path(value['collector_root'])
    expected = manifest(root, workspace, value['implementation_revision'])
    q.require(q.same_typed(value, expected), 'guard semantic mismatch or source/prefix drift')
    plan, _, _, committed, _ = runner.read(root, workspace)
    for row in committed[3:]:
        directory = root / 'attempts' / plan['jobs'][row['slot']]['slot_id']
        original = q.loads(q.regular(directory, 'base_backend_result.json').read_bytes())
        gate = audit(directory, original, value)
        stored = q.loads(q.regular(directory, 'fast_arm_gate.json').read_bytes())
        final = q.loads(q.regular(directory, 'result.json').read_bytes())
        q.require(q.same_typed(gate, stored) and q.same_typed(final, guarded_result(original, gate, expected_sha)),
                  'unguarded continuation or fast-arm evidence mismatch')
    return root, value


def status(path, expected_sha, workspace):
    root, _ = verify(path, expected_sha, workspace)
    result = runner.status(root, workspace)
    result.update(guard_sha256=expected_sha, guard_verified=True, dispatch_authorized=False,
                  read_only_model_calls=0, read_only_native_episodes_executed=0)
    return result


class GuardedBackend:
    def __init__(self, backend, path, expected_sha, workspace):
        self.backend, self.path, self.sha, self.workspace = backend, path, expected_sha, workspace

    def boundary(self, root, plan, completed):
        bound, _ = verify(self.path, self.sha, self.workspace)
        q.require(bound.resolve() == root.resolve(), 'guard collector differs')
        self.backend.boundary(root, plan, completed)

    def dependencies(self, root, plan, job):
        verify(self.path, self.sha, self.workspace)
        q.require(job['arm'] == 'hybrid' and job['slot'] in (3, 4, 5), 'guard cannot dispatch new or FSM slots')
        if hasattr(self.backend, 'dependencies'): self.backend.dependencies(root, plan, job)

    def execute(self, directory, job, plan):
        _, binding = verify(self.path, self.sha, self.workspace)
        original = self.backend.execute(directory, job, plan)
        runner.write(directory / 'base_backend_result.json', original)
        gate = audit(directory, original, binding)
        runner.write(directory / 'fast_arm_gate.json', gate)
        return guarded_result(original, gate, self.sha)


def run(path, expected_sha, workspace, backend, max_slots=1):
    q.require(type(max_slots) is int and 1 <= max_slots <= 3, 'Hybrid continuation max-slots must be 1..3')
    root, _ = verify(path, expected_sha, workspace)
    state = runner.status(root, workspace)
    q.require(state['resume_allowed'] is True and state['completed_slots'] >= 3,
              'stopped, complete or unknown continuation cannot resume')
    return runner.run(root, workspace, GuardedBackend(backend, path, expected_sha, workspace), max_slots)
