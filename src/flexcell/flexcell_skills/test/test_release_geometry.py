"""Independent geometry and phase-selection counterexamples, without ROS."""
import importlib.util
import math
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / 'scripts/release_geometry.py'


def api():
    assert SCRIPT.is_file(), 'release geometry analysis has not been implemented'
    spec = importlib.util.spec_from_file_location('release_geometry_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    return dict(parent=[0., 0., 0., 0., 0., 0., 1.],
                box=[.126, 0., -.16, 0., 0., 0., 1.],
                parent_box_reference=[.126, 0., -.16, 0., 0., 0., 1.],
                parent_ee=[.126, 0., 0., 0., 0., 0., 1.],
                ee_target=[.126, 0., 0.], box_goal=[.126, 0., -.172],
                clearance_m=.012, settled=[.126, 0., -.172])


def test_vertical_control_has_no_tracking_or_geometry_error():
    result = api().decompose(**inputs())
    assert result['components']['ee_tracking']['norm_m'] == 0.
    assert result['components']['rigid_geometry']['norm_m'] < 1e-15
    assert result['components']['rigid_residual']['norm_m'] == 0.
    assert result['final_error']['norm_m'] == 0.


def test_rotating_carried_offset_is_not_a_world_vertical_offset():
    data = inputs()
    data['parent'][3:] = [0., math.sqrt(.5), 0., math.sqrt(.5)]
    data['box'][:3] = [-.16, 0., -.126]
    data['settled'] = [-.16, 0., -.138]
    result = api().decompose(**data)
    assert result['components']['rigid_geometry']['xyz_m'] == pytest.approx([-.16, 0., .16])
    assert result['components']['rigid_geometry']['horizontal_m'] == pytest.approx(.16)
    assert result['components']['rigid_residual']['norm_m'] < 1e-15
    assert result['component_sum_xyz_m'] == pytest.approx(result['final_error']['xyz_m'])


def test_nonzero_components_can_cancel_and_norms_must_not_be_added():
    data = inputs()
    data['parent'][0] = .01
    data['parent_box_reference'][0] -= .01
    result = api().decompose(**data)
    assert result['components']['ee_tracking']['norm_m'] == pytest.approx(.01)
    assert result['components']['rigid_geometry']['norm_m'] == pytest.approx(.01)
    assert result['final_error']['norm_m'] == 0.


@pytest.mark.parametrize('field,value', [('parent',[0.]*7), ('box',[0.,0.,0.,0.,0.,0.,2.]),
    ('ee_target',[0.,0.,float('nan')]), ('box_goal',[True,0.,0.]),
    ('settled',[0.,0.]), ('clearance_m',float('inf'))])
def test_bad_geometry_is_rejected(field, value):
    data = inputs()
    data[field] = value
    with pytest.raises(ValueError):
        api().decompose(**data)


def trace(states):
    return [dict(sim_ns=(i+1)*2_000_000, step_ns=2_000_000,
                 monotonic_ns=(i+1)*3_000_000,
                 parent_pose=inputs()['parent'],
                 objects={'target_box_a':dict(joint_component=state, pose=inputs()['box'])})
            for i,state in enumerate(states)]


def test_selects_only_declared_task_session_and_retains_adjacent_release_steps():
    rows = trace([True, True, False, False, True, True, False, False])
    result = api().attachment_interval(rows, 'target_box_a', 9_000_000, 24_000_000)
    assert result['first_attached']['sim_ns'] == 10_000_000
    assert result['last_attached']['sim_ns'] == 12_000_000
    assert result['first_detached']['sim_ns'] == 14_000_000


@pytest.mark.parametrize('states', [[False,False,False], [False,True,True],
    [True,True,False], [False,True,False,True,False], [False,1,False]])
def test_missing_ambiguous_or_unbounded_session_is_rejected(states):
    rows=trace(states)
    with pytest.raises(ValueError):
        api().attachment_interval(rows, 'target_box_a', rows[0]['monotonic_ns'], rows[-1]['monotonic_ns'])


@pytest.mark.parametrize('kind', ['missing_step','duplicate','monotonic_regression','bad_step'])
def test_bad_physics_timeline_is_rejected(kind):
    rows=trace([False, False, True, True, False, False])
    if kind == 'missing_step': del rows[2]
    if kind == 'duplicate': rows.insert(2, rows[2])
    if kind == 'monotonic_regression': rows[2]['monotonic_ns']=rows[1]['monotonic_ns']
    if kind == 'bad_step': rows[2]['step_ns']=1
    with pytest.raises(ValueError):
        api().attachment_interval(rows, 'target_box_a', rows[0]['monotonic_ns'], rows[-1]['monotonic_ns'])


def cdr():
    return (SCRIPT.parent.parent / 'setup/acceptance/legacy_release_20261101/tf-static-1.cdr').read_bytes()


def test_real_cdr_matches_the_independently_ros_decoded_fixed_transforms():
    module = api()
    assert callable(getattr(module, 'decode_tf_static', None)), 'offline CDR decoder is absent'
    assert module.decode_tf_static(cdr()) == [
        dict(parent='link5', child='end_effector_link', stamp_ns=0,
             pose=[.126,0.,0.,0.,0.,0.,1.]),
        dict(parent='world', child='link1', stamp_ns=0,
             pose=[0.,0.,0.,0.,0.,0.,1.])]


@pytest.mark.parametrize('kind', ['unsupported_encoding','truncated','trailing_bytes','invalid_quaternion'])
def test_corrupt_static_cdr_is_rejected(kind):
    module=api()
    assert callable(getattr(module, 'decode_tf_static', None)), 'offline CDR decoder is absent'
    data=bytearray(cdr())
    if kind == 'unsupported_encoding': data[1]=0
    if kind == 'truncated': del data[-1:]
    if kind == 'trailing_bytes': data.extend(b'bad')
    if kind == 'invalid_quaternion': data[-8:]=b'\0'*8
    with pytest.raises(ValueError):
        module.decode_tf_static(bytes(data))
