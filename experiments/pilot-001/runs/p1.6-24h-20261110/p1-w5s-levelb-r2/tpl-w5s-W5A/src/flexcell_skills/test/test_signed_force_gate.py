"""A support force must be signed: on the target, along the declared direction."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from signed_force_gate import FROZEN, verify_file

STEP = 2_000_000
SETTLE_FROM, SETTLE_TO = 1_000_000_000, 2_000_000_000


def declaration():
    return dict(settle_from_ns=SETTLE_FROM, settle_to_ns=SETTLE_TO, step_ns=STEP,
                signed_force={key: FROZEN[key] for key in
                              ('target', 'partner', 'direction', 'magnitude_min_n',
                               'magnitude_max_n', 'max_lateral_n', 'min_signed_samples')})


def contacts(points, partner='ground_plane::link::col'):
    return {'contact': [dict(collision1=dict(id=9, name='target_box_a::link::col'),
                             collision2=dict(id=6, name=partner),
                             position=[{}] * len(points), depth=[0.] * len(points), normal=[{}] * len(points),
                             wrench=[dict(body_1_wrench=dict(force=dict(x=p[0], y=p[1], z=p[2])),
                                          body_2_wrench=dict(force=dict(x=-p[0], y=-p[1], z=-p[2])))
                                     for p in points])]}


def write(path, *, points, partner='ground_plane::link::col', samples=501):
    rows = []
    for index in range(samples):
        ns = SETTLE_FROM + index * STEP
        rows.append(dict(
            sim_ns=ns, step_ns=STEP, monotonic_ns=10 ** 12 + 2 * ns, source='ECM_POST_PHYSICS',
            targets={'target_box_a': dict(collision_entity=9, component_present=True,
                                          pose=[0., 0., .0175, 0., 0., 0., 1.],
                                          contacts=contacts(points, partner))}))
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return path


def test_four_support_points_sum_to_the_declared_weight(tmp_path):
    path = write(tmp_path / 'contact_steps.jsonl', points=[[0., 0., .1225]] * 4)
    result = verify_file(path, declaration())
    assert result['status'] == 'SIGNED_FORCE_PASS'
    assert result['samples'] == 501 and result['known_direction_only'] is True
    assert result['min_z_n'] == pytest.approx(.49) and result['max_lateral_n'] < 1e-12


def test_inverted_support_is_refused(tmp_path):
    path = write(tmp_path / 'contact_steps.jsonl', points=[[0., 0., -.1225]] * 4)
    with pytest.raises(ValueError, match='gravity direction'):
        verify_file(path, declaration())


def test_lateral_bleed_on_a_vertical_support_is_refused(tmp_path):
    path = write(tmp_path / 'contact_steps.jsonl', points=[[.01, 0., .12]] * 4)
    with pytest.raises(ValueError, match='not along the declared direction|lateral force component'):
        verify_file(path, declaration())


def test_a_different_contact_partner_is_refused(tmp_path):
    path = write(tmp_path / 'contact_steps.jsonl', points=[[0., 0., .1225]] * 4,
                 partner='open_manipulator_x::link5::col')
    with pytest.raises(ValueError, match='not the declared one'):
        verify_file(path, declaration())


def test_short_coverage_is_refused(tmp_path):
    path = write(tmp_path / 'contact_steps.jsonl', points=[[0., 0., .1225]] * 4, samples=100)
    with pytest.raises(ValueError, match='coverage below declaration'):
        verify_file(path, declaration())


def test_changed_fixture_is_refused(tmp_path):
    path = write(tmp_path / 'contact_steps.jsonl', points=[[0., 0., .1225]] * 4)
    spec = declaration()
    spec['signed_force'] = dict(spec['signed_force'], max_lateral_n=.01)
    with pytest.raises(ValueError, match='fixture changed'):
        verify_file(path, spec)
