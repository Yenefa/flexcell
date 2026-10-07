import json
from pathlib import Path
import pytest

import qualification_prepare as q
import bounded_runner as runner
from bounded_live import LiveBackend, result_json, uncertain, transport_unknown
from test_qualification_prepare import fixture


@pytest.fixture
def collection(tmp_path, fixture):
    workspace = fixture['workspace']
    for rel in runner.EXECUTOR_FILES:
        p = workspace / rel
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text('frozen executor fixture\n')
    package = tmp_path / 'package'
    result = q.prepare(package, **fixture)
    root = tmp_path / 'collection'
    runner.register(root, package, result['package_sha256'], workspace, fixture['history_root'], fixture['budget_path'], 'c'*40)
    return root, workspace, package, result['package_sha256']


class FakeBackend:
    def __init__(self, outcomes=None, failure_boundary=None, rc=0):
        self.calls = []; self.boundaries = 0; self.outcomes = outcomes or {}; self.failure_boundary = failure_boundary; self.rc = rc
    def boundary(self, root, plan, completed):
        self.boundaries += 1
        if self.boundaries == self.failure_boundary: raise ValueError('confirmed boundary failure')
    def execute(self, directory, job, plan):
        self.calls.append(job['slot'])
        return {'outcome': self.outcomes.get(job['slot'], 'SUCCEEDED'), 'native_episode_ids':
                ['episode-%d-%d' % (job['slot'], i) for i in range(job['native_episode_limit'])], 'client_return_code': self.rc}


def test_preview_registration_does_not_dispatch_and_caps_development(collection):
    root, workspace, package, sha = collection
    preview = runner.preview(package, sha, workspace)
    assert preview['full_schedule_slots'] == 450 and len(preview['jobs']) == 6
    assert preview['native_episode_limit'] == 10 and not preview['dispatch_authorized']
    assert not preview['qualification_sampling_authorized'] and preview['n_ge_50'] == 'FROZEN'
    assert runner.status(root, workspace)['state'] == 'REGISTERED'
    assert not list((root / 'attempts').iterdir())


def test_pause_at_committed_boundary_resume_once_and_exact_quota(collection):
    root, workspace, _, _ = collection; backend = FakeBackend()
    first = runner.run(root, workspace, backend, max_slots=2)
    assert first['state'] == 'PAUSED' and first['native_episode_count'] == 2
    assert first['resume_allowed'] and backend.calls == [0,1]
    final = runner.run(root, workspace, backend)
    assert final['state'] == 'COMPLETE' and final['all_trials_succeeded']
    assert final['native_episode_count'] == final['native_dispatch_quota_used'] == 10
    assert backend.calls == [0,1,2,3,4,5]
    with pytest.raises(ValueError, match='cannot resume'): runner.run(root, workspace, backend)
    assert backend.calls == [0,1,2,3,4,5]


def test_known_target_failure_retained_without_replacement(collection):
    root, workspace, _, _ = collection; backend = FakeBackend({0:'FAILED'})
    result = runner.run(root, workspace, backend)
    assert result['development_complete'] and not result['all_trials_succeeded']
    assert result['outcomes'] == ['FAILED'] + ['SUCCEEDED']*5
    assert backend.calls == [0,1,2,3,4,5]


def test_source_failure_stops_before_remaining_source_slot(collection):
    root, workspace, _, _ = collection; backend = FakeBackend({4:'FAILED'})
    result = runner.run(root, workspace, backend)
    assert result['state'] == 'STOPPED' and backend.calls == [0,1,2,3,4]
    assert not result['resume_allowed'] and result['native_episode_count'] == 9


@pytest.mark.parametrize('outcome', ['UNKNOWN','HARNESS_ERROR'])
def test_uncertain_or_harness_failure_never_resumes(collection, outcome):
    root, workspace, _, _ = collection; backend = FakeBackend({0:outcome})
    result = runner.run(root, workspace, backend)
    assert result['state'] == 'STOPPED' and backend.calls == [0]
    with pytest.raises(ValueError): runner.run(root, workspace, backend)
    assert backend.calls == [0]


def test_claim_before_process_loss_is_unknown_tail(collection):
    root, workspace, _, _ = collection
    plan, rows, *_ = runner.read(root, workspace)
    runner.append(root, rows, 'CLAIMED', slot=0)
    assert runner.status(root, workspace)['state'] == 'UNKNOWN_TAIL'
    backend = FakeBackend()
    with pytest.raises(ValueError): runner.run(root, workspace, backend)
    assert not backend.calls


def test_incomplete_journal_never_runs(collection):
    root, workspace, _, _ = collection
    with (root / 'events.jsonl').open('ab') as f: f.write(b'{"seq":')
    backend = FakeBackend()
    with pytest.raises(ValueError, match='incomplete'): runner.run(root, workspace, backend)
    assert not backend.calls


def test_committed_evidence_drift_prevents_resumption(collection):
    root, workspace, _, _ = collection
    runner.run(root, workspace, FakeBackend(), max_slots=1)
    (root / 'attempts/00-T1-fsm/result.json').write_text('{}')
    backend = FakeBackend()
    with pytest.raises(ValueError, match='drift'): runner.run(root, workspace, backend)
    assert not backend.calls


def test_unregistered_artifact_in_committed_attempt_is_rejected(collection):
    root, workspace, _, _ = collection
    runner.run(root, workspace, FakeBackend(), max_slots=1)
    (root / 'attempts/00-T1-fsm/extra.json').write_text('{}')
    with pytest.raises(ValueError, match='artifact set'): runner.status(root, workspace)


def test_changed_executor_cannot_resume_existing_trial(collection):
    root, workspace, _, _ = collection
    (workspace / runner.EXECUTOR_FILES[0]).write_text('changed runner')
    backend = FakeBackend()
    with pytest.raises(ValueError, match='executor source drift'): runner.run(root, workspace, backend)
    assert not backend.calls


@pytest.mark.parametrize('slots', [0,7,50,True,1.0])
def test_large_or_coercive_slot_count_refused(collection, slots):
    root, workspace, _, _ = collection; backend = FakeBackend()
    with pytest.raises(ValueError): runner.run(root, workspace, backend, slots)
    assert not backend.calls


@pytest.mark.parametrize('rc', [-6,134,139,None,True])
def test_earlier_success_json_cannot_override_process_failure(collection, rc):
    root, workspace, _, _ = collection; backend = FakeBackend(rc=rc)
    result = runner.run(root, workspace, backend)
    assert result['state'] == 'STOPPED' and result['outcomes'] == ['UNKNOWN']
    assert not result['all_trials_succeeded'] and backend.calls == [0]


def test_budget_or_idle_boundary_failure_stops_before_claim(collection):
    root, workspace, _, _ = collection; backend = FakeBackend(failure_boundary=1)
    result = runner.run(root, workspace, backend)
    assert result['state'] == 'STOPPED' and result['completed_slots'] == 0 and not backend.calls


def test_boundary_failure_after_terminal_preserves_completed_trial(collection):
    root, workspace, _, _ = collection; backend = FakeBackend(failure_boundary=2)
    result = runner.run(root, workspace, backend)
    assert result['state'] == 'STOPPED' and result['outcomes'] == ['SUCCEEDED'] and backend.calls == [0]


@pytest.mark.parametrize('raw', ['RESULT {"action_status":true,"outcome_val":0}',
    'RESULT {"action_status":4,"outcome_val":false}', 'RESULT {"action_status":4,"outcome_val":0,"x":1e999}',
    'RESULT {"action_status":4,"action_status":6,"outcome_val":0}', 'RESULT {} RESULT {}'])
def test_strict_client_terminal_parser(raw):
    with pytest.raises(ValueError): result_json(raw)


def test_client_status_and_transport_uncertainty(tmp_path):
    assert result_json('GOAL_UUID abc\nRESULT {"action_status":4,"outcome_val":0}')['action_status'] == 4
    assert uncertain({'return_code':-6}) and uncertain({'return_code':None})
    p = tmp_path / 'move_to_pose_transport.jsonl'
    p.write_text('{"event":"goal_response_unknown"}\n')
    assert transport_unknown(tmp_path)


def local_collection(collection):
    old, workspace, package, sha = collection
    runner.run(old, workspace, FakeBackend(failure_boundary=1))
    plan = q.loads((old / 'plan.json').read_bytes())
    root = old.parent / 'local-first'
    runner.register(root, package, sha, workspace, Path(plan['history_path']),
                    Path(plan['budget_path']), 'd'*40, order='local-first', predecessor=old)
    return root, workspace


def test_local_first_preserves_task_set_and_total_quota(collection):
    _, workspace, package, sha = collection
    paired = runner.preview(package, sha, workspace)
    local = runner.preview(package, sha, workspace, 'local-first')
    identity = lambda jobs: {(j['case_id'], j['arm'], q.digest(j['request']), q.digest(j['initial_objects'])) for j in jobs}
    assert identity(paired['jobs']) == identity(local['jobs'])
    assert [j['arm'] for j in local['jobs']] == ['fsm']*3 + ['hybrid']*3
    assert [j['axis'] for j in local['jobs'][:3]] == ['T1','T3','S1']
    assert sum(j['native_episode_limit'] for j in local['jobs'][:3]) == 5
    assert local['native_episode_limit'] == 10 and local['n_ge_50'] == 'FROZEN'


def test_local_prefix_pauses_with_hybrid_slots_still_unclaimed(collection):
    root, workspace = local_collection(collection)
    backend = FakeBackend({0:'FAILED'})
    result = runner.run(root, workspace, backend, max_slots=3)
    assert result['state'] == 'PAUSED' and result['native_dispatch_quota_used'] == 5
    assert result['outcomes'] == ['FAILED','SUCCEEDED','SUCCEEDED']
    assert result['pending_jobs'] == [{'axis':axis,'arm':'hybrid'} for axis in ('T1','T3','S1')]
    final = runner.run(root, workspace, backend)
    assert final['state'] == 'COMPLETE' and backend.calls == list(range(6))
    assert final['native_episode_count'] == 10 and not final['all_trials_succeeded']


def test_source_failure_in_local_prefix_stops_before_hybrid(collection):
    root, workspace = local_collection(collection)
    backend = FakeBackend({2:'FAILED'})
    result = runner.run(root, workspace, backend, max_slots=3)
    assert result['state'] == 'STOPPED' and backend.calls == [0,1,2]
    assert result['native_dispatch_quota_used'] == 5


def test_remote_dependency_failure_consumes_no_new_slot(collection):
    root, workspace = local_collection(collection)
    class OfflineHybrid(FakeBackend):
        def dependencies(self, root, plan, job):
            if job['arm'] == 'hybrid': raise ValueError('remote dependency offline')
    backend = OfflineHybrid()
    first = runner.run(root, workspace, backend, max_slots=3)
    assert first['state'] == 'PAUSED' and backend.calls == [0,1,2]
    stopped = runner.run(root, workspace, backend)
    assert stopped['state'] == 'STOPPED' and backend.calls == [0,1,2]
    assert stopped['native_dispatch_quota_used'] == 5


def test_claimed_predecessor_cannot_be_replaced(collection):
    old, workspace, package, sha = collection
    runner.run(old, workspace, FakeBackend(), max_slots=1)
    with pytest.raises(ValueError, match='claimed or completed'):
        runner.predecessor_pin(old, sha, workspace)


def test_predecessor_drift_prevents_local_resume(collection):
    root, workspace = local_collection(collection)
    link = q.loads((root / 'plan.json').read_bytes())['predecessor']
    with (Path(link['root']) / 'events.jsonl').open('ab') as stream: stream.write(b'{}\n')
    backend = FakeBackend()
    with pytest.raises(ValueError):runner.run(root, workspace, backend)
    assert not backend.calls


def test_live_fsm_dependencies_do_not_touch_remote_probe(tmp_path):
    backend = LiveBackend.__new__(LiveBackend)
    def forbidden():raise AssertionError('FSM must not read model connection')
    backend.current = forbidden
    backend.dependencies(tmp_path, {}, {'arm':'fsm'})
