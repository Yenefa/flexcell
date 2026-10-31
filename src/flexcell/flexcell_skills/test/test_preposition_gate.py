"""The pre-attach reference must be measured, contact-free and then held by the carry."""
import json
import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from preposition_gate import FROZEN, verify_run

STEP = 2_000_000
ATTACH = 1_000_000_000
HOLD = FROZEN['hold_ns'] // STEP
LAST = ATTACH + 40 * STEP


def pose(x, z):
    return [x, 0., z, 0., 0., 0., 1.]


def build(root, *, counterpart='ground_plane::link::collision', component=True,
          parent_drift=0., attach_jump=0.):
    parent, child = pose(.095, .19), pose(.22, .0175)
    physics, contacts = [], []
    for index in range(-HOLD - 2, 42):
        ns = ATTACH + index * STEP
        if ns < 0:
            continue
        attached = ATTACH <= ns <= LAST
        drift = parent_drift * (index + HOLD + 2) if not attached else 0.
        jump = attach_jump if ns == ATTACH else 0.
        parent_pose = pose(.095 + drift, .19 + drift)
        child_pose = pose(.22 + jump, .0175 + jump)
        clock = dict(sim_ns=ns, step_ns=STEP, monotonic_ns=10 ** 12 + 2 * ns)
        physics.append(dict(clock, parent_pose=parent_pose, objects={
            'target_box_a': dict(pose=child_pose, joint_component=attached),
            'target_box_b': dict(pose=pose(.22, .2), joint_component=False)}))
        ground = dict(position=[{}], depth=[0.], normal=[{}], collision1=dict(id=7, name='target_box_a::link::col'),
                      collision2=dict(id=9, name=counterpart),
                      wrench=[dict(body_1_wrench=dict(force=dict(z=.49)),
                                   body_2_wrench=dict(force=dict(z=-.49)))])
        contacts.append(dict(clock, schema_version=1, source='ECM_POST_PHYSICS', targets={
            'target_box_a': dict(collision_entity=7, component_present=component, pose=child_pose,
                                 contacts=dict(contact=[ground]) if component else None),
            'target_box_b': dict(collision_entity=8, component_present=True, pose=pose(.22, .2), contacts={}),
            'ground_plane': dict(collision_entity=9, component_present=False,
                                 pose=[0., 0., 0., 0., 0., 0., 1.], contacts=None)}))
    follow = dict(object='target_box_a', session='b' * 32, samples=40, max_translation_m=1e-7,
                  max_rotation_rad=1e-9, fault='', active=False, first_sim_ns=ATTACH, last_sim_ns=LAST,
                  reference_source='preposition', attach_jump_translation_m=attach_jump,
                  attach_jump_rotation_rad=0.,
                  preposition=dict(samples=5, window_ns=80_000_000, spread_m=1e-7, spread_rad=1e-9,
                                   reference=pose(.125, -.1725),
                                   contact_freedom='NOT_OBSERVABLE_ON_POSE_TOPIC'))
    skills = root / 'skills'
    skills.mkdir(parents=True)
    (skills / 'carry.jsonl').write_text(json.dumps(dict(event='follow_final', object='target_box_a',
                                                        session='b' * 32, follow=follow)) + '\n')
    (root / 'physics_steps.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in physics))
    (root / 'contact_steps.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in contacts))
    return dict(preposition_gate=FROZEN)


def test_contact_free_at_rest_reference_is_enforced_over_the_whole_carry(tmp_path):
    declaration = build(tmp_path)
    result = verify_run(tmp_path, 'target_box_a', declaration)
    assert result['status'] == 'PREPOSITION_REFERENCE_PASS'
    assert result['hold']['samples'] == HOLD
    assert result['hold']['counterparts'] == ['ground_plane::link::collision']
    assert result['attached']['steps'] == 41
    assert result['attached']['max_translation_m'] < 1e-6
    assert result['runtime']['agreement_m'] < 1e-9
    assert result['contact_freedom'] == 'RAW_CONTACT_SENSOR_PRE_ATTACH_ONLY'
    assert result['default_admission'] == 'NO_GO'


def test_arm_contact_before_attachment_stops_the_window(tmp_path):
    declaration = build(tmp_path, counterpart='open_manipulator_x::link5::col')
    with pytest.raises(ValueError, match='before attachment'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_missing_contact_component_is_unknown_not_contact_free(tmp_path):
    declaration = build(tmp_path, component=False)
    with pytest.raises(ValueError, match='unavailable'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_moving_arm_cannot_pose_a_reference(tmp_path):
    declaration = build(tmp_path, parent_drift=.00004)
    with pytest.raises(ValueError, match='not at rest'):
        verify_run(tmp_path, 'target_box_a', declaration)


@pytest.mark.parametrize('motion', ['translation', 'rotation'])
def test_common_world_motion_is_not_a_stationary_raw_hold(tmp_path, motion):
    declaration = build(tmp_path)
    path = tmp_path / 'physics_steps.jsonl'
    frames = [json.loads(line) for line in path.read_text().splitlines()]
    for row in frames:
        elapsed = (row['sim_ns'] - ATTACH) / 1e9
        for value in [row['parent_pose']] + [o['pose'] for o in row['objects'].values()]:
            if motion == 'translation':
                value[0] += .5 * elapsed
            else:
                angle = .05 * elapsed
                x, y = value[:2]
                value[:2] = [math.cos(angle)*x-math.sin(angle)*y,
                             math.sin(angle)*x+math.cos(angle)*y]
                value[3:] = [0., 0., math.sin(angle/2), math.cos(angle/2)]
    path.write_text(''.join(json.dumps(row)+'\n' for row in frames))
    with pytest.raises(ValueError, match='not at rest'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_stationary_raw_hold_accepts_equivalent_quaternion_signs(tmp_path):
    declaration = build(tmp_path)
    path = tmp_path / 'physics_steps.jsonl'
    frames = [json.loads(line) for line in path.read_text().splitlines()]
    for index, row in enumerate(frames):
        if index % 2:
            child = row['objects']['target_box_a']['pose']
            child[3:] = [-v for v in child[3:]]
    path.write_text(''.join(json.dumps(row)+'\n' for row in frames))
    report = verify_run(tmp_path, 'target_box_a', declaration)
    assert report['status'] == 'PREPOSITION_REFERENCE_PASS'
    assert report['preposition_reference'][:3] == pytest.approx([.125, 0., -.1725])
    assert abs(report['preposition_reference'][-1]) == pytest.approx(1.)


def test_binding_jump_breaks_the_pre_attach_constraint(tmp_path):
    declaration = build(tmp_path, attach_jump=.01)
    with pytest.raises(ValueError, match='(drifted|moved)'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_changed_thresholds_are_refused(tmp_path):
    declaration = build(tmp_path)
    declaration['preposition_gate'] = dict(FROZEN, spread_translation_m=.01)
    with pytest.raises(ValueError, match='thresholds changed'):
        verify_run(tmp_path, 'target_box_a', declaration)
