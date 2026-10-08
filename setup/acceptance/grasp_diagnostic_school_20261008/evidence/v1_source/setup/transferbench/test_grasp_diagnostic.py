"""Direct probes must stop on unknown ownership and preserve known failures."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import grasp_diagnostic as g
import qualification_prepare as q


def command(outcome=0, rc=None):
    result = dict(action='pick', goal_uuid='a' * 32, outcome_val=outcome,
                  action_status=(4, 6, 5)[outcome], error_code='ERR_NONE' if outcome == 0 else 'ERR_GRASP_FAILED',
                  grasp_attached=outcome == 0, motion_error_code=0,
                  evidence_id='measured-grasp', detail='measured result')
    return dict(return_code=(0 if outcome == 0 else 1) if rc is None else rc,
                stdout='GOAL_UUID ' + result['goal_uuid'] + '\nRESULT ' + json.dumps(result) + '\n', stderr='')


def record(outcome=0):
    value = dict(object_name=q.OBJECTS[0], evidence_id='measured-grasp', outcome=str(outcome),
                 status=(1, 2, 4)[outcome], error_code=0 if outcome == 0 else 23,
                 motion_error_code=0, detail='measured result', box_before=[.22, 0., .0175])
    if outcome == 0:
        value.update(box_after=[.22, 0., .1175], carry_offset=[0., 0., -.16],
                     attach_gap_m=.16, box_rise_m=.1, carry_engage_confirmed=True)
    return value


@pytest.fixture
def registered(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    for rel in g.TOOL_FILES:
        path = workspace / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('frozen source\n')
    deployment = tmp_path / 'deployment.json'
    g.write(deployment, dict(policy='fsm', threshold=.85, runtime_fingerprint='f' * 64))
    protected = tmp_path / 'protected'; protected.mkdir(); (protected / 'episode.json').write_text('{}\n')
    monkeypatch.setattr(g, 'module', lambda _: SimpleNamespace(verify_deployment=lambda d, w: None))
    root = tmp_path / 'diagnostic'
    result = g.register(root, workspace, deployment, 'b' * 40, [protected])
    return root, result['plan_sha256'], workspace, protected


class FakeBackend:
    def __init__(self, *, mode='', fail_first=False):
        self.mode = mode; self.fail_first = fail_first; self.calls = []; self.active = q.OBJECTS[0]
        self.count = 0

    def health(self, directory, plan):
        self.calls.append(('health', directory.parent.name))
        if self.mode == 'health': raise ValueError('unavailable')

    def reset(self, directory, name): self.calls.append((name, directory.name))
    def clear(self, directory, target): self.active = target; self.calls.append(('clear', target))

    def observe(self, directory, name):
        self.calls.append((name, directory.name))
        if self.mode == 'post_observe' and name == 'observe_after': raise ValueError('observe unavailable')
        return dict(outcome_val=0, carry=dict(engaged=False, object_id=''),
                    objects=[dict(name=n, available=True, position=p) for n, p in q.SOURCE.items()])

    def offsets(self): return {}

    def pick(self, directory, target):
        self.count += 1; self.calls.append(('pick', target))
        value = command(1 if self.fail_first and self.count == 1 else 0)
        if self.mode == 'timeout': value.update(return_code=4, stdout='CLIENT_TIMEOUT\n')
        if self.mode == 'signal': value['return_code'] = -6
        g.write(directory / 'pick.json', value)
        self.last = value; return value

    def capture(self, directory, before):
        directory.mkdir()
        outcome = 1 if self.fail_first and self.count == 1 else 0
        value = record(outcome); value['object_name'] = self.active
        if self.mode == 'nested_timeout':
            value['detail'] = 'gripper close failed: gripper result timeout'
        (directory / 'pick.jsonl').write_text(json.dumps(value) + '\n')
        events = [dict(kind='controller_transport', event='controller_goal_send_requested', controller_goal_uuid='c' * 32)]
        if self.mode != 'controller_unknown':
            events.append(dict(kind='controller_transport', event='controller_goal_terminal', controller_goal_uuid='c' * 32, status=4))
        (directory / 'controller_transport.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))


def test_fixed_two_objects_and_exclusive_root(registered):
    root, sha, workspace, protected = registered
    before = g.files(root)
    assert g.status(root, sha, workspace)['state'] == 'REGISTERED'
    assert g.files(root) == before and not (root / 'execution').exists()
    with pytest.raises(ValueError, match='new and regular'):
        g.register(root, workspace, Path(q.loads((root / 'plan.json').read_bytes())['deployment']), 'b' * 40, [protected])


@pytest.mark.parametrize('mode', ['timeout', 'signal', 'controller_unknown'])
def test_unknown_stops_without_reset_or_next_pick(registered, mode):
    root, sha, workspace, _ = registered; backend = FakeBackend(mode=mode)
    report = g.run(root, sha, workspace, backend)
    assert report['state'] == 'STOPPED' and report['pick_goals'] == 1
    assert [c for c in backend.calls if c[0] == 'pick'] == [('pick', q.OBJECTS[0])]
    assert not [c for c in backend.calls if c[0] == 'reset_after']
    saved = g.files(root)
    with pytest.raises(FileExistsError): g.run(root, sha, workspace, backend)
    assert g.files(root) == saved and backend.count == 1


def test_known_failure_is_preserved_and_next_predeclared_object_can_run(registered):
    root, sha, workspace, protected = registered; backend = FakeBackend(fail_first=True)
    report = g.run(root, sha, workspace, backend)
    assert report['state'] == 'COMPLETE' and report['pick_goals'] == 2
    assert [r['outcome'] for r in report['trials']] == ['FAILED', 'SUCCEEDED']
    assert len([c for c in backend.calls if c[0] == 'reset_after']) == 2
    assert (protected / 'episode.json').read_text() == '{}\n'
    assert report['mechanism_root_cause'] == 'UNKNOWN' and not report['ready_for_large_test']


def test_post_observe_failure_cleans_only_known_terminal_then_stops(registered):
    root, sha, workspace, _ = registered; backend = FakeBackend(mode='post_observe')
    report = g.run(root, sha, workspace, backend)
    assert report['state'] == 'STOPPED' and len(report['trials']) == 1
    assert len([c for c in backend.calls if c[0] == 'reset_after']) == 1
    assert backend.count == 1


def test_unavailable_health_sends_no_motion(registered):
    root, sha, workspace, _ = registered; backend = FakeBackend(mode='health')
    result = g.run(root, sha, workspace, backend)
    assert result['state'] == 'STOPPED' and result['pick_goals'] == 0
    assert [c[0] for c in backend.calls] == ['health']


@pytest.mark.parametrize('rc', [-6, 134, -11, 139, False, 4])
def test_green_json_cannot_hide_signal_unknown_or_coercive_exit(rc):
    with pytest.raises(ValueError): g.result_json(command(rc=rc), 'pick')


@pytest.mark.parametrize('key,value', [('grasp_attached', False), ('outcome_val', False),
                                      ('action_status', '4'), ('goal_uuid', 'd' * 32)])
def test_default_or_mismatched_success_result_fails(key, value):
    cmd = command(); result = q.loads(cmd['stdout'].split('RESULT ')[1]); result[key] = value
    cmd['stdout'] = 'GOAL_UUID ' + 'a' * 32 + '\nRESULT ' + json.dumps(result) + '\n'
    with pytest.raises(ValueError): g.result_json(cmd, 'pick')


@pytest.mark.parametrize('key', ['box_before', 'box_after', 'carry_offset', 'attach_gap_m', 'box_rise_m', 'carry_engage_confirmed'])
def test_missing_measured_success_evidence_never_becomes_zero(key):
    raw = record(); del raw[key]
    with pytest.raises(ValueError): g.audit_pick(g.result_json(command(), 'pick'), [raw], q.OBJECTS[0])


def test_failed_pick_has_no_fabricated_after_pose_or_rise():
    result = g.audit_pick(g.result_json(command(1), 'pick'), [record(1)], q.OBJECTS[0])
    assert result['outcome'] == 'FAILED' and 'box_rise_m' not in result['measured']
    assert result['carry_engage_confirmed'] == 'NOT_MEASURED' and result['decision_latency_ms'] == 'NOT_RUN'


def test_known_top_level_abort_cannot_hide_nested_gripper_timeout():
    cmd = command(1); result = g.result_json(cmd, 'pick'); raw = record(1)
    result['detail'] = raw['detail'] = 'gripper close failed: gripper result timeout'
    with pytest.raises(ValueError, match='ownership unknown'): g.audit_pick(result, [raw], q.OBJECTS[0])


def test_protected_evidence_drift_refuses_dispatch(registered):
    root, sha, workspace, protected = registered
    (protected / 'episode.json').write_text('{"changed": true}\n')
    backend = FakeBackend()
    with pytest.raises(ValueError, match='protected evidence changed'): g.run(root, sha, workspace, backend)
    assert backend.calls == [] and not (root / 'execution').exists()


def test_instrument_drift_refuses_dispatch(registered):
    root, sha, workspace, _ = registered; (workspace / g.TOOL_FILES[0]).write_text('different\n')
    with pytest.raises(ValueError, match='source changed'): g.run(root, sha, workspace, FakeBackend())
    assert not (root / 'execution').exists()


def test_default_cli_inspects_without_importing_ros_or_creating_claim(registered):
    root, sha, workspace, _ = registered
    cmd = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / '136_grasp_diagnostic.py'),
        'run', '--root', str(root), '--workspace', str(workspace), '--expected-sha256', sha], capture_output=True, text=True)
    assert cmd.returncode == 0 and json.loads(cmd.stdout)['state'] == 'REGISTERED'
    assert not (root / 'execution').exists()
