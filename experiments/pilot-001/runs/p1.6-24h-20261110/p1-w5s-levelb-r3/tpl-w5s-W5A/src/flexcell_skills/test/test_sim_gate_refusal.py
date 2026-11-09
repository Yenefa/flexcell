"""Exercise the real smoke verdict with synthetic commands; no ROS or motion."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
REFUSAL = {
    'object_name': 'target_box_a', 'outcome': '1', 'error_code': 25,
    'released': False,
    'release_attitude': 'release tilt 0.372 deg exceeds 0.1 deg limit; carry held',
    'detail': 'attached object attitude rejected before release; carry held: '
              'release tilt 0.372 deg exceeds 0.1 deg limit; carry held',
}
FAILED_TASK = {'outcome_val': 1, 'error_code': 'ERR_SKILL_FAILED', 'object_at_place': False}
SUCCEEDED_TASK = {'outcome_val': 0, 'error_code': 'ERR_NONE', 'object_at_place': True}


@pytest.fixture
def run_smoke(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('gate_refusal_smoke', ROOT / 'scripts/sim_smoke.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    commands = []

    def run(task, places, verifies=(), case='gate_refusal', task_rc=None, picks=()):
        def profile(out, *args, **kwargs):
            params, world = out / 'params.yaml', out / 'world.sdf'
            params.write_text('{}')
            world.write_text('<sdf><world name="synthetic"/></sdf>')
            return params, world

        def command(argv, out, timeout=120):
            commands.append(out.name)
            if out.name == 'task':
                skills = out.parent / 'skills'
                skills.mkdir()
                for name, rows in (('pick', picks), ('place', places), ('verify', verifies)):
                    (skills / (name + '.jsonl')).write_text(''.join(json.dumps(r) + '\n' for r in rows))
                out.with_suffix('.stdout').write_text('RESULT ' + json.dumps(task))
                return (0 if task['outcome_val'] == 0 else 1) if task_rc is None else task_rc
            out.with_suffix('.stdout').write_text(json.dumps(dict(ok=True, hard_fail=[],
                checks=dict(task_state='IDLE', carry_engaged=False))))
            return 0

        monkeypatch.setattr(module, 'profile', profile)
        monkeypatch.setattr(module, 'command', command)
        monkeypatch.setattr(module.subprocess, 'Popen',
                            lambda *a, **k: SimpleNamespace(returncode=0, poll=lambda: None))
        monkeypatch.setattr(module, 'remember_owned', lambda *a: None)
        monkeypatch.setattr(module, 'terminate_owned', lambda *a: None)
        monkeypatch.setattr(module.time, 'sleep', lambda *a: None)
        monkeypatch.setattr(sys, 'argv', ['sim_smoke', '--out', str(tmp_path), '--case', case])
        rc = module.main()
        result = json.loads(next(tmp_path.glob('run-*/result.json')).read_text())
        return rc, result, commands
    return run


def test_gate_refusal_cannot_pass_as_a_successful_place(run_smoke):
    row = dict(REFUSAL, outcome='0', released=True, carry_release_confirmed=True,
               release_attitude='release tilt 0.02 deg within 5.0 deg', detail='placed')
    rc, result, commands = run_smoke(SUCCEEDED_TASK, [row], [{'outcome': '0'}])
    assert rc == 1
    assert result['status'] == 'ROBOT_FAILURE'
    assert result.get('expectation_met') is not True
    assert 'reset_after' not in commands


def test_real_typed_gate_refusal_satisfies_the_negative_control(run_smoke):
    rc, result, commands = run_smoke(FAILED_TASK, [REFUSAL])
    assert rc == 0 and result['status'] == 'EXPECTED_FAILURE'
    assert result['expectation_met'] is True
    assert 'reset_after' in commands


@pytest.mark.parametrize('defect', [
    'no_place', 'released', 'confirmed_release', 'unrelated_error', 'wrong_outcome',
    'wrong_object', 'verified', 'duplicate_place', 'wrong_task_error', 'object_at_goal',
    'wrong_place_error',
])
def test_missing_or_contradictory_refusal_evidence_fails(run_smoke, defect):
    task, row = deepcopy(FAILED_TASK), deepcopy(REFUSAL)
    places, verifies = [row], []
    if defect == 'no_place': places = []
    elif defect == 'released': row['released'] = True
    elif defect == 'confirmed_release': row['carry_release_confirmed'] = True
    elif defect == 'unrelated_error': row['detail'] = 'deadline exceeds budget; carry held'
    elif defect == 'wrong_outcome': row['outcome'] = '0'
    elif defect == 'wrong_place_error': row['error_code'] = 2
    elif defect == 'wrong_object': row['object_name'] = 'target_box_b'
    elif defect == 'verified': verifies = [{'outcome': '1'}]
    elif defect == 'duplicate_place': places.append(deepcopy(row))
    elif defect == 'wrong_task_error': task['error_code'] = 'ERR_RECOVERY_EXHAUSTED'
    elif defect == 'object_at_goal': task['object_at_place'] = True
    rc, result, _ = run_smoke(task, places, verifies)
    assert rc == 1 and result['status'] == 'ROBOT_FAILURE'
    assert result.get('expectation_met') is not True


@pytest.mark.parametrize('task_rc', [-11, 124, 0])
def test_abnormal_or_contradictory_command_exit_cannot_pass(run_smoke, task_rc):
    rc, result, _ = run_smoke(FAILED_TASK, [REFUSAL], task_rc=task_rc)
    assert rc == 1 and result['status'] == 'ROBOT_FAILURE'


@pytest.mark.parametrize('field', ['released', 'carry_release_confirmed'])
def test_release_in_another_skill_cannot_be_hidden(run_smoke, field):
    rc, result, _ = run_smoke(FAILED_TASK, [REFUSAL], picks=[{field: True}])
    assert rc == 1 and result['status'] == 'ROBOT_FAILURE'


def test_ordinary_success_still_passes(run_smoke):
    rc, result, _ = run_smoke(SUCCEEDED_TASK, [], case='normal')
    assert rc == 0 and result['status'] == 'PASS'
