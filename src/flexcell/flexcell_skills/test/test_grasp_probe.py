"""Exercise diagnostic dispatch/measurement boundaries without ROS or Gazebo."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


@pytest.fixture
def probe():
    path = Path(__file__).resolve().parents[4] / 'setup/111_grasp_probe.py'
    spec = importlib.util.spec_from_file_location('grasp_probe_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pose(x=.20, y=-.18, z=.0175, measured=True):
    return NS(position=NS(x=x, y=y, z=z),
              orientation=NS(x=0., y=0., z=0., w=1. if measured else 0.))


def pick_result(failure=False):
    return NS(outcome=1 if failure else 0, error_code=23 if failure else 0,
              status=2 if failure else 1, grasp_attached=not failure,
              object_pose_before=pose(), object_pose_after=pose(z=.016 if failure else .11),
              evidence_id='pick-ev', detail='physical pick result')


def meta(error=None, terminal=True, status=4):
    return dict(accepted=True, terminal_confirmed=terminal, ros_status=status,
                harness_error=error, goal_uuid='goal')


class Future:
    def __init__(self, value=None, complete=True, schedule=(), error=None):
        self.value, self.complete, self.schedule, self.error = value, complete, list(schedule), error

    def done(self):
        return self.complete

    def result(self):
        if self.error:
            raise self.error
        return self.value if self.complete else None


class Executor:
    def spin_until_future_complete(self, future, timeout_sec):
        if future.schedule:
            future.complete = future.schedule.pop(0)


class Handle:
    def __init__(self, result, accepted=True):
        self.result_future, self.accepted, self.cancels = result, accepted, 0
        self.goal_id = NS(uuid=list(range(16)))

    def get_result_async(self):
        return self.result_future

    def cancel_goal_async(self):
        self.cancels += 1
        return Future(NS(goals_canceling=[self.goal_id]))


class Client:
    def __init__(self, future):
        self.future, self.goals = future, []

    def send_goal_async(self, goal):
        self.goals.append(goal)
        return self.future


def test_unknown_acceptance_never_resends(probe):
    client = Client(Future(complete=False))
    result, audit = probe.call_action(Executor(), client, 'goal', 1., 1.)
    assert result is None and audit['accepted'] is None
    assert not audit['terminal_confirmed'] and audit['harness_error']
    assert client.goals == ['goal']


@pytest.mark.parametrize('late', [False, True])
def test_result_timeout_cancels_once_and_requires_terminal_reply(probe, late):
    reply = NS(status=5, result=pick_result(failure=True))
    future = Future(reply, complete=False, schedule=[False, late])
    handle = Handle(future)
    client = Client(Future(handle))
    result, audit = probe.call_action(Executor(), client, 'goal', 1., 1.)
    assert handle.cancels == 1 and client.goals == ['goal']
    assert audit['cancel_acknowledged'] and audit['harness_error']
    assert audit['terminal_confirmed'] is late
    assert (result is reply.result) is late


@pytest.mark.parametrize('mode', ['rejected', 'unknown_status', 'result_exception'])
def test_invalid_transport_result_cannot_pass(probe, mode):
    future = Future(NS(status=0, result=pick_result()))
    if mode == 'result_exception':
        future.error = RuntimeError('lost result')
    handle = Handle(future, accepted=mode != 'rejected')
    _, audit = probe.call_action(Executor(), Client(Future(handle)), 'goal', 1., 1.)
    assert audit['harness_error']
    assert audit['terminal_confirmed'] is (mode == 'rejected')


@pytest.mark.parametrize('defect', ['default_status', 'false_attached', 'failed_outcome',
                                  'default_pose', 'nonfinite_pose', 'zero_rise', 'overflow_rise'])
def test_error_zero_is_not_sufficient_pick_evidence(probe, defect):
    result = pick_result()
    if defect == 'default_status':
        result.status = 0
    elif defect == 'false_attached':
        result.grasp_attached = False
    elif defect == 'failed_outcome':
        result.outcome = 1
    elif defect == 'default_pose':
        result.object_pose_after = pose(x=0., y=0., z=0., measured=False)
    elif defect == 'nonfinite_pose':
        result.object_pose_after.position.z = float('nan')
    elif defect == 'overflow_rise':
        result.object_pose_before.position.z = -1e308
        result.object_pose_after.position.z = 1e308
    else:
        result.object_pose_after = pose()
    row = probe.capture_pick(result, meta())
    assert not row['pick_ok'] and row['harness_error']
    json.dumps(row, allow_nan=False)


def test_unmeasured_failed_pose_does_not_invent_negative_rise(probe):
    result = pick_result(failure=True)
    result.object_pose_after = pose(x=0., y=0., z=0., measured=False)
    row = probe.capture_pick(result, meta(status=6))
    assert row['error_code'] == 23 and row['rise_m'] is None
    assert not row.get('harness_error')


class Transport:
    def __init__(self, mode='good'):
        self.mode, self.calls, self.closed = mode, [], False

    def ready(self):
        return True

    def prepare(self):
        self.calls.append('prepare')
        return dict(ok=self.mode != 'precondition')

    def pick(self, object_name):
        self.calls.append(('pick', object_name))
        if self.mode == 'timeout':
            return None, meta(error='timeout', terminal=False, status=None)
        result = pick_result(failure=self.mode == 'physical_failure')
        if self.mode == 'ghost':
            result.grasp_attached = False
        return result, meta(status=6 if self.mode == 'physical_failure' else 4)

    def place(self, object_name, position):
        self.calls.append(('place', object_name, position))
        result = NS(outcome=0, error_code=0, status=1, released=self.mode != 'release_ghost',
                    evidence_id='place-ev', detail='placed', object_pose_after=pose())
        return result, meta()

    def reset(self):
        self.calls.append('cleanup')
        return dict(ok=self.mode != 'cleanup')

    def close(self):
        self.closed = True


def args(tmp_path):
    return NS(trials=2, object='target_box_b', out=str(tmp_path/'probe.jsonl'), settle_s=0., release_s=0.)


def test_b_box_returns_to_its_measured_start_and_repeats_only_after_reset(probe, tmp_path):
    transport = Transport()
    rows = probe.run_probe(args(tmp_path), transport, sleep=lambda _: None)
    assert len(rows) == 2 and all(r['pick_ok'] for r in rows)
    trial = ['prepare', ('pick', 'target_box_b'),
             ('place', 'target_box_b', [.20, -.18, .0175]), 'cleanup']
    assert transport.calls == trial * 2
    assert all(r['evidence_id'] == 'pick-ev' for r in rows)


@pytest.mark.parametrize('mode', ['timeout', 'ghost', 'precondition', 'cleanup', 'release_ghost'])
def test_harness_failure_is_flushed_and_stops_trial_loop(probe, tmp_path, mode):
    transport = Transport(mode)
    rows = probe.run_probe(args(tmp_path), transport, sleep=lambda _: None)
    saved = [json.loads(line) for line in (tmp_path/'probe.jsonl').read_text().splitlines()]
    assert len(rows) == len(saved) == 1 and saved[0]['harness_error']
    assert transport.calls.count('prepare') == 1
    if mode == 'timeout':
        assert 'cleanup' not in transport.calls
        assert not any(isinstance(x, tuple) and x[0] == 'place' for x in transport.calls)
    if mode == 'release_ghost':
        assert saved[0]['pick_ok']  # physical pick evidence is retained


def test_real_grasp_failures_are_retained_and_next_trial_requires_reset(probe, tmp_path):
    transport = Transport('physical_failure')
    rows = probe.run_probe(args(tmp_path), transport, sleep=lambda _: None)
    assert len(rows) == 2 and all(r['error_code'] == 23 for r in rows)
    assert all(r['rise_m'] < 0 and not r['harness_error'] for r in rows)
    assert transport.calls == ['prepare', ('pick', 'target_box_b'), 'cleanup'] * 2


def test_existing_evidence_is_never_truncated(probe, tmp_path):
    config = args(tmp_path)
    Path(config.out).write_text('retained failure\n')
    transport = Transport()
    with pytest.raises(FileExistsError):
        probe.run_probe(config, transport)
    assert Path(config.out).read_text() == 'retained failure\n'
    assert not transport.calls


def test_failed_injection_clear_prevents_pick(probe, monkeypatch):
    transport = probe.RosProbe.__new__(probe.RosProbe)
    monkeypatch.setattr(transport, 'reset', lambda: dict(ok=True))
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return NS(returncode=1, stdout='clear not sealed', stderr='')
    monkeypatch.setattr(probe.subprocess, 'run', run)
    assert not transport.prepare()['ok']
    command = commands[0]
    assert command[command.index('--inject') + 1] == ''
    assert command[command.index('--expect-inject-state') + 1] == 'cleared'


@pytest.mark.parametrize('rc,payload,expected', [(0, {'ok': True}, True), (139, {'ok': True}, False),
    (0, {'ok': False, 'nested': {'ok': True}}, False), (0, {'ok': 'true'}, False),
    (0, [], False), (0, 'broken JSON', False)])
def test_reset_requires_clean_exit_and_top_level_boolean_ok(probe, monkeypatch, rc, payload, expected):
    transport = probe.RosProbe.__new__(probe.RosProbe)
    transport.args = NS(reset_timeout_s=1.)
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(probe.subprocess, 'run', lambda *a, **k: NS(returncode=rc, stdout=stdout, stderr=''))
    assert transport.reset()['ok'] is expected


@pytest.mark.parametrize('mode,exit_code', [('good', 0), ('ghost', 1), ('timeout', 1), ('physical_failure', 0)])
def test_cli_exit_status_and_cleanup(probe, monkeypatch, tmp_path, mode, exit_code):
    transport = Transport(mode)
    monkeypatch.setattr(probe, 'RosProbe', lambda _: transport)
    monkeypatch.setattr(probe.sys, 'argv', ['probe', '--trials', '2', '--out', str(tmp_path/'probe.jsonl'),
                                         '--object', 'target_box_b', '--settle-s', '0', '--release-s', '0'])
    assert probe.main() == exit_code and transport.closed
