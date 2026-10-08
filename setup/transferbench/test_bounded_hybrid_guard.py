from pathlib import Path
import subprocess
import sys

import pytest

import bounded_hybrid_guard as guard
import bounded_runner as runner
import qualification_prepare as q
from test_bounded_runner import collection, FakeBackend, local_collection
from test_qualification_prepare import fixture, dump


@pytest.fixture
def guarded(collection, tmp_path):
    root, workspace = local_collection(collection)
    for rel in guard.TOOL_FILES:
        target = workspace / rel; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('guard source fixture\n')
    runner.run(root, workspace, FakeBackend(), max_slots=3)
    path = tmp_path / 'resume_guard.json'
    result = guard.register(path, root, workspace, 'e' * 40)
    return root, workspace, path, result['guard_sha256']


def model_episode(run_id, binding, *, mode='fast'):
    fast_identity = binding['model_identity']
    sha = fast_identity['calibration_sha256']
    trace = {'source': 'llm' if mode != 'fast' else 'jev', 'fallback': False,
             'threshold': .85, 'calibration_sha256': sha, 'proposals': []}
    fast = {'source': 'jev', 'fallback': False, 'calibration': sha,
            'calibration_sha256': sha, 'confidence_calibrated': True, 'tokens': 400,
            'model': fast_identity['model'], 'model_sha256': fast_identity['model_sha256']}
    if mode == 'skip': trace['proposals'] = [{'policy': 'jev', 'skipped': True}]
    elif mode != 'missing': trace['proposals'] = [{'policy': 'jev', 'policy_trace': fast}]
    if mode == 'zero': fast['tokens'] = 0
    if mode == 'bool': fast['tokens'] = True
    if mode == 'wrong_cal': fast['calibration_sha256'] = 'f' * 64
    if mode == 'fallback': trace.update(source='fsm', fallback=True)
    return {'run_id': run_id, 'runtime_fingerprint': binding['runtime_fingerprint'],
            'policy': {'name': 'hybrid'}, 'steps': [{'seq': 1,
                'policy_input': {'world_state_canonical': '{}'},
                'policy_output': {'policy_trace': trace}}]}


class EpisodeBackend(FakeBackend):
    def __init__(self, binding, modes=None, **kwargs):
        super().__init__(**kwargs)
        self.binding = binding; self.modes = modes or {}

    def execute(self, directory, job, plan):
        original = super().execute(directory, job, plan)
        original.update(runtime_fingerprint=self.binding['runtime_fingerprint'],
                        calibration_sha256=self.binding['model_identity']['calibration_sha256'], stop=False)
        dump(directory / 'client.json', {'return_code': self.rc})
        dump(directory / 'deployment.json', {'policy': 'hybrid', 'threshold': .85,
              'runtime_fingerprint': self.binding['runtime_fingerprint'],
              'active_backends': {'fast': self.binding['model_identity']}})
        for i, run_id in enumerate(original['native_episode_ids']):
            dump(directory / 'episodes' / (run_id + '.json'), model_episode(run_id, self.binding,
                 mode=self.modes.get((job['slot'], i), self.modes.get(job['slot'], 'fast'))))
        return original


def backend(guarded, **kwargs):
    return EpisodeBackend(q.loads(guarded[2].read_bytes()), **kwargs)


def test_registration_and_default_status_are_model_free_and_preserve_prefix(guarded):
    root, workspace, path, sha = guarded
    before = (root / 'events.jsonl').read_bytes()
    result = guard.status(path, sha, workspace)
    assert result['state'] == 'PAUSED' and result['completed_slots'] == 3
    assert result['native_episode_count'] == 5 and result['guard_verified']
    assert not result['dispatch_authorized'] and result['read_only_model_calls'] == 0
    assert (root / 'events.jsonl').read_bytes() == before
    assert not list((root / 'attempts').glob('*hybrid'))


@pytest.mark.parametrize('mode', ['skip', 'missing'])
def test_old_green_zero_fast_result_stops_before_next_hybrid(guarded, mode):
    root, workspace, path, sha = guarded
    native = backend(guarded, modes={3: mode})
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert native.calls == [3] and result['state'] == 'STOPPED'
    assert result['outcomes'][-1] == 'HARNESS_ERROR'
    assert result['native_episode_count'] == 6 and not result['resume_allowed']
    folder = root / 'attempts/03-T1-hybrid'
    assert q.loads((folder / 'base_backend_result.json').read_bytes())['outcome'] == 'SUCCEEDED'
    audit = q.loads((folder / 'fast_arm_gate.json').read_bytes())
    assert audit['fast_calls'] == audit['fast_tokens'] == 0 and not audit['ok']
    assert guard.status(path, sha, workspace)['guard_verified']
    with pytest.raises(ValueError, match='cannot resume'):
        guard.run(path, sha, workspace, native)
    assert native.calls == [3]


def test_all_slow_selections_with_real_fast_proposals_remain_valid(guarded):
    root, workspace, path, sha = guarded
    native = backend(guarded, modes={3: 'slow', 4: 'slow', 5: 'slow'})
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert result['state'] == 'COMPLETE' and result['all_trials_succeeded']
    assert result['native_episode_count'] == result['native_dispatch_quota_used'] == 10
    assert native.calls == [3, 4, 5]
    audit = q.loads((root / 'attempts/04-T3-hybrid/fast_arm_gate.json').read_bytes())
    assert audit['fast_selected'] == 0 and audit['fast_calls'] == 3 and audit['fast_tokens'] == 1200
    assert guard.status(path, sha, workspace)['guard_verified']


def test_one_good_composite_component_cannot_hide_missing_fast_in_another(guarded):
    root, workspace, path, sha = guarded
    native = backend(guarded, modes={(4, 1): 'missing'})
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert native.calls == [3, 4] and result['state'] == 'STOPPED'
    gate = q.loads((root / 'attempts/04-T3-hybrid/fast_arm_gate.json').read_bytes())
    assert gate['fast_calls'] == 2 and not gate['ok']
    assert not (root / 'attempts/05-S1-hybrid').exists()


@pytest.mark.parametrize('mode', ['zero', 'bool', 'wrong_cal', 'fallback'])
def test_invalid_fast_provenance_fails_before_next_dispatch(guarded, mode):
    root, workspace, path, sha = guarded
    native = backend(guarded, modes={3: mode})
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert result['state'] == 'STOPPED' and result['outcomes'][-1] == 'HARNESS_ERROR'
    assert native.calls == [3]


@pytest.mark.parametrize('rc', [-6, 134, 139, None, True, 2])
def test_process_failure_cannot_be_hidden_by_green_native_json(guarded, rc):
    root, workspace, path, sha = guarded
    native = backend(guarded, rc=rc)
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert result['state'] == 'STOPPED' and not result['all_trials_succeeded']
    assert native.calls == [3]
    assert q.loads((root / 'attempts/03-T1-hybrid/base_backend_result.json').read_bytes())['client_return_code'] == rc


def test_known_native_failure_is_retained_and_can_advance_if_provenance_passes(guarded):
    root, workspace, path, sha = guarded
    native = backend(guarded, outcomes={3: 'FAILED'})
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert result['state'] == 'COMPLETE' and not result['all_trials_succeeded']
    assert result['outcomes'][3:] == ['FAILED', 'SUCCEEDED', 'SUCCEEDED']
    assert native.calls == [3, 4, 5]


def test_native_failure_with_missing_provenance_stays_failed_and_halts(guarded):
    root, workspace, path, sha = guarded
    native = backend(guarded, outcomes={3: 'FAILED'}, modes={3: 'missing'})
    result = guard.run(path, sha, workspace, native, max_slots=3)
    assert result['state'] == 'STOPPED' and result['outcomes'][-1] == 'FAILED'
    assert not q.loads((root / 'attempts/03-T1-hybrid/fast_arm_gate.json').read_bytes())['ok']
    assert native.calls == [3]


def test_guard_survives_committed_pause_then_continues_once(guarded):
    root, workspace, path, sha = guarded
    native = backend(guarded)
    first = guard.run(path, sha, workspace, native)
    assert first['state'] == 'PAUSED' and native.calls == [3]
    assert guard.status(path, sha, workspace)['completed_slots'] == 4
    last = guard.run(path, sha, workspace, native, max_slots=2)
    assert last['state'] == 'COMPLETE' and native.calls == [3, 4, 5]


@pytest.mark.parametrize('field,value', [('qualification_sampling_authorized', True),
     ('baseline_native_episodes', False), ('remaining_native_episode_cap', 50), ('guard_source_sha256', {})])
def test_resealed_manifest_cannot_unlock_or_change_guard_identity(guarded, field, value):
    root, workspace, path, sha = guarded
    altered = q.loads(path.read_bytes()); altered[field] = value; path.write_bytes(q.encoded(altered))
    with pytest.raises(ValueError, match='expected digest'): guard.status(path, sha, workspace)
    with pytest.raises(ValueError, match='semantic mismatch'): guard.status(path, q.sha(path), workspace)


def test_source_drift_prevents_execution_before_claim(guarded):
    root, workspace, path, sha = guarded
    before = (root / 'events.jsonl').read_bytes()
    native = backend(guarded)
    (workspace / guard.TOOL_FILES[0]).write_text('changed guard\n')
    with pytest.raises(ValueError, match='drift'): guard.run(path, sha, workspace, native)
    assert not native.calls and (root / 'events.jsonl').read_bytes() == before


def test_unguarded_continuation_cannot_be_laundered_into_guard_receipt(guarded):
    root, workspace, path, sha = guarded
    native = backend(guarded)
    runner.run(root, workspace, native, max_slots=1)
    with pytest.raises(ValueError): guard.status(path, sha, workspace)
    with pytest.raises(ValueError): guard.run(path, sha, workspace, native)
    assert native.calls == [3]


@pytest.mark.parametrize('slots', [0, 4, 50, True, 1.0])
def test_no_large_or_coercive_continuation(guarded, slots):
    root, workspace, path, sha = guarded
    native = backend(guarded)
    with pytest.raises(ValueError): guard.run(path, sha, workspace, native, slots)
    assert not native.calls and runner.status(root, workspace)['completed_slots'] == 3


def test_existing_guard_is_never_overwritten(guarded):
    root, workspace, path, sha = guarded
    with pytest.raises(ValueError, match='already exists'): guard.register(path, root, workspace, 'e' * 40)
    assert q.sha(path) == sha


def test_default_cli_run_is_read_only_and_preserves_collector(guarded):
    root, workspace, path, sha = guarded
    before = (root / 'events.jsonl').read_bytes()
    # Actual subprocess exercises argparse and its default branch, not a mocked CLI.
    script = Path(__file__).resolve().parents[1] / '135_bounded_hybrid_resume.py'
    completed = subprocess.run([sys.executable, str(script), 'run', '--guard', str(path),
             '--expected-sha256', sha, '--workspace', str(workspace)], capture_output=True)
    assert completed.returncode == 0
    report = q.loads(completed.stdout)
    assert report['guard_verified'] and not report['dispatch_authorized']
    assert (root / 'events.jsonl').read_bytes() == before
