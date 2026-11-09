"""Independent evidence must reject a claimed follow when the trace disagrees."""
import importlib.util
import json
import math
from pathlib import Path
import pytest


def gate():
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location('joint_follow_gate', root / 'scripts/joint_follow_gate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def fixture(tmp_path):
    (tmp_path / 'skills').mkdir(); (tmp_path / 'data').mkdir()
    token = 'a' * 32
    summary = dict(object='target_box_a', session=token, samples=3, active=False, fault='',
        translation_limit_m=.002, rotation_limit_rad=math.pi/180,
        max_translation_m=0., max_rotation_rad=0., first_sim_ns=20_000_000,
        last_sim_ns=60_000_000, first_relative_pose=[.1, 0., 0., 0., 0., 0., 1.])
    start = dict(event='start', backend='detachable_joint', object='target_box_a', session=token)
    end = dict(event='follow_final', object='target_box_a', session=token, follow=summary)
    write_rows(tmp_path / 'skills/carry.jsonl', [start, end])
    for name in ('pick', 'place'):
        write_rows(tmp_path / ('skills/%s.jsonl' % name), [dict(object_name='target_box_a', outcome='0',
            joint_follow_watch=dict(session=token, fault=''))])
    physics = [dict(sim_ns=i*20_000_000, monotonic_ns=i*20_000_000,
        physics_steps=10, physics_min_step_ns=2_000_000, physics_max_step_ns=2_000_000,
        physics_bad_time=False, physics_missing_pose_steps=0, physics_nonfinite_pose=False,
        physics_max_pose_jump_m=0., contact_force_observed=False,
        parent_pose=[0., 0., 0., 0., 0., 0., 1.], objects={'target_box_a': dict(
        pose=[.1, 0., 0., 0., 0., 0., 1.], joint_component=True),
        'target_box_b': dict(pose=[0., -.2, 0., 0., 0., 0., 1.], joint_component=False)}) for i in range(1, 4)]
    write_rows(tmp_path / 'data/physics.jsonl', physics)
    steps = [dict(sim_ns=i*2_000_000, step_ns=2_000_000, monotonic_ns=i*2_000_000,
        parent_pose=[0., 0., 0., 0., 0., 0., 1.], objects={'target_box_a': dict(
        pose=[.1, 0., 0., 0., 0., 0., 1.], joint_component=True),
        'target_box_b': dict(pose=[0., -.2, 0., 0., 0., 0., 1.], joint_component=False)},
        contact_force_observed=False) for i in range(10, 31)]
    write_rows(tmp_path / 'physics_steps.jsonl', steps)
    return physics


def test_complete_correlated_trace_passes(tmp_path):
    fixture(tmp_path)
    result = gate().verify_run(tmp_path, 'target_box_a', physics_step_ns=2_000_000)
    assert result['status'] == 'FOLLOW_TRACE_PASS' and result['attached_samples'] == 3
    assert result['physics_step_samples'] == 21


def test_drift_hidden_between_50_hz_samples_is_rejected(tmp_path):
    fixture(tmp_path)
    path = tmp_path / 'physics_steps.jsonl'
    steps = [json.loads(line) for line in path.read_text().splitlines()]
    steps[5]['objects']['target_box_a']['pose'][2] = -.07
    write_rows(path, steps)
    with pytest.raises(ValueError, match='per-step SE'):
        gate().verify_run(tmp_path, 'target_box_a', physics_step_ns=2_000_000)


def test_duration_and_real_step_checks_cannot_be_inferred_from_a_label(tmp_path):
    rows = fixture(tmp_path)
    with pytest.raises(ValueError, match='duration'):
        gate().verify_run(tmp_path, 'target_box_a', min_duration_s=10.)
    rows[1]['physics_max_step_ns'] = 5_000_000
    write_rows(tmp_path / 'data/physics.jsonl', rows)
    with pytest.raises(ValueError, match='physics-step'):
        gate().verify_run(tmp_path, 'target_box_a', physics_step_ns=2_000_000)


@pytest.mark.parametrize('defect', ['drift', 'missing_frame', 'false_attached', 'wrong_session',
                                     'latched_fault', 'looser_tolerance'])
def test_bad_follow_or_mismatched_evidence_stops_window(tmp_path, defect):
    physics = fixture(tmp_path)
    if defect == 'drift': physics[1]['objects']['target_box_a']['pose'][2] = -.07
    if defect == 'missing_frame': physics.pop(1)
    if defect == 'false_attached': physics[1]['objects']['target_box_a']['joint_component'] = False
    if defect in ('drift', 'missing_frame', 'false_attached'):
        write_rows(tmp_path / 'data/physics.jsonl', physics)
    if defect == 'wrong_session':
        write_rows(tmp_path / 'skills/place.jsonl', [dict(object_name='target_box_a', outcome='0',
            joint_follow_watch=dict(session='b'*32, fault=''))])
    if defect in ('latched_fault', 'looser_tolerance'):
        path = tmp_path / 'skills/carry.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]['follow']['fault' if defect == 'latched_fault' else 'translation_limit_m'] = (
            'bad follow' if defect == 'latched_fault' else .005)
        write_rows(path, rows)
    with pytest.raises(ValueError):
        gate().verify_run(tmp_path, 'target_box_a')
