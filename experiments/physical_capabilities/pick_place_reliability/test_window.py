"""Offline driver tests for the four-slot pick/place window.

Covers the seven cases the handoff requires before any real Gazebo run:
success, task failure, nested directory, multiple results, missing file,
outer timeout, unknown terminal state.
"""
import json
from pathlib import Path

import pytest

import run_window as rw


def write_result(directory, case='normal', status='PASS', run_name='run-test', **extra):
    run = Path(directory) / run_name
    run.mkdir(parents=True, exist_ok=True)
    payload = dict(case=case, status=status,
                   task=dict(outcome='OUTCOME_SUCCEEDED', error_code='ERR_NONE'),
                   **extra)
    path = run / 'result.json'
    path.write_text(json.dumps(payload))
    return path


def test_success_returns_one_result(tmp_path):
    write_result(tmp_path / 'NORMAL_1', 'normal')
    result, path = rw.one_result(tmp_path / 'NORMAL_1', 'normal')
    assert result['status'] == 'PASS'
    assert rw.classify(result, 0) == 'OK'


def test_task_failure_is_not_ok(tmp_path):
    write_result(tmp_path / 'NORMAL_1', 'normal', status='ROBOT_FAILURE')
    result, _ = rw.one_result(tmp_path / 'NORMAL_1', 'normal')
    assert rw.classify(result, 0) == 'TASK_FAILED'


def test_nested_directory_is_not_accepted(tmp_path):
    nested = tmp_path / 'NORMAL_1' / 'run-test' / 'sub'
    nested.mkdir(parents=True)
    (nested / 'result.json').write_text(json.dumps(dict(case='normal', status='PASS')))
    with pytest.raises(ValueError):
        rw.one_result(tmp_path / 'NORMAL_1', 'normal')


def test_multiple_results_are_rejected(tmp_path):
    write_result(tmp_path / 'NORMAL_1', 'normal', run_name='run-first')
    write_result(tmp_path / 'NORMAL_1', 'normal', run_name='run-second')
    with pytest.raises(ValueError):
        rw.one_result(tmp_path / 'NORMAL_1', 'normal')


def test_missing_file_is_rejected(tmp_path):
    (tmp_path / 'NORMAL_1').mkdir()
    with pytest.raises(ValueError):
        rw.one_result(tmp_path / 'NORMAL_1', 'normal')


def test_case_mismatch_is_rejected(tmp_path):
    write_result(tmp_path / 'NORMAL_1', 'dual_object')
    with pytest.raises(ValueError):
        rw.one_result(tmp_path / 'NORMAL_1', 'normal')


def test_outer_timeout_stops_following_slots(tmp_path):
    prereg = dict(slots=[dict(label='A', case='normal'), dict(label='B', case='normal')],
                  slot_timeout_s=1, window_budget_s=1000,
                  backend='velocity_servo', skill_backend='legacy')

    def runner(label, case, slot_out, index):
        Path(slot_out).mkdir(parents=True, exist_ok=True)
        return 124

    payload = rw.run_window(prereg, tmp_path / 'out', runner=runner)
    assert payload['results'][0]['status'] == 'UNKNOWN'
    assert payload['results'][1]['status'] == 'NOT_RUN'
    assert payload['all_slots_completed'] is False


def test_unknown_terminal_stops_following_slots(tmp_path):
    prereg = dict(slots=[dict(label='A', case='normal'), dict(label='B', case='normal')],
                  slot_timeout_s=10, window_budget_s=1000,
                  backend='velocity_servo', skill_backend='legacy')

    def runner(label, case, slot_out, index):
        Path(slot_out).mkdir(parents=True, exist_ok=True)
        if label == 'A':
            write_result(slot_out, 'normal', status='STATE_UNKNOWN')
        return 0

    payload = rw.run_window(prereg, tmp_path / 'out', runner=runner)
    assert payload['results'][0]['status'] == 'UNKNOWN'
    assert payload['results'][1]['status'] == 'NOT_RUN'


@pytest.mark.parametrize('payload', [
    dict(status='STATE_UNKNOWN'),
    dict(status='ACTION_TERMINAL_UNKNOWN'),
    dict(motion_terminal_known=False),
    dict(terminal_known=False),
    dict(error_code=33),
    dict(nested=dict(error_code=33)),
    dict(nested=[dict(terminal_known=False)]),
])
def test_unknown_detector(payload):
    assert rw.unknown(payload) is True


def test_unknown_detector_accepts_clean_result():
    assert rw.unknown(dict(status='PASS', error_code='ERR_NONE')) is False
