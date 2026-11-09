"""Reject cross-cohort joins, missing force observations and non-ballistic release."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from integrated_contact_gate import verify_evidence


def fixture():
    limits = dict(prebind_ns=1_000_000_000, postrelease_ns=500_000_000,
                  freefall_ns=40_000_000, max_clock_skew_ns=50_000_000,
                  min_weight_samples=476, force_mean_min_n=.392, force_mean_max_n=.588)
    declaration = dict(contact_trace=True, physics_step_s=.002, release_clearance_m=.05, contact_gate=limits)
    lo, hi, release = 1_000_000_000, 1_040_000_000, 1_042_000_000
    physics, contacts = [], []
    for ns in range(0, release + 500_000_001, 2_000_000):
        z = .1 if ns < release else .1 - 4.9*((ns-release)/1e9)**2
        a, b = [0., 0., z, 0., 0., 0., 1.], [0., .2, .0175, 0., 0., 0., 1.]
        clock = dict(sim_ns=ns, step_ns=2_000_000, monotonic_ns=10**12 + 2*ns)
        physics.append(dict(clock, objects={'target_box_a': dict(pose=a, joint_component=lo <= ns < release),
                                           'target_box_b': dict(pose=b, joint_component=False)}))
        weight = dict(contact=[dict(collision1=dict(id='8'), collision2=dict(id='9'), position=[{}],
            wrench=[dict(body_1_wrench=dict(force=dict(z=.49)), body_2_wrench=dict(force=dict(z=-.49)))])])
        contacts.append(dict(clock, schema_version=1, source='ECM_POST_PHYSICS', targets={
            'target_box_a': dict(collision_entity=7, component_present=True, pose=a.copy(), contacts={}),
            'target_box_b': dict(collision_entity=8, component_present=True, pose=b.copy(), contacts=weight),
            'ground_plane': dict(collision_entity=9, component_present=False, pose=[0., 0., 0., 0., 0., 0., 1.], contacts=None)}))
    return physics, contacts, lo, hi, declaration


def test_same_round_force_controls_and_fixed_freefall_interval():
    p, c, lo, hi, d = fixture()
    result = verify_evidence(p, c, 'target_box_a', lo, hi, d)
    assert result['status'] == 'INTEGRATED_CONTACT_RELEASE_PASS'
    assert result['weight_samples'] == 500 and result['mean_weight_force_n'] == .49
    assert result['freefall']['acceleration_m_s2'] == pytest.approx(-9.8)
    assert result['freefall']['samples'] == 21 and result['default_admission'] == 'NO_GO'
    assert result['preposition_reference_qualified'] is False


@pytest.mark.parametrize('defect', ['missing', 'cohort', 'pose', 'unknown', 'alias', 'nan', 'early_contact', 'gravity'])
def test_incomplete_or_conflicting_evidence_is_rejected(defect):
    p, c, lo, hi, d = fixture()
    if defect == 'missing': c.pop(20)
    elif defect == 'cohort':
        for row in c: row['monotonic_ns'] += 10**9
    elif defect == 'pose': c[40]['targets']['target_box_a']['pose'][2] += .001
    elif defect == 'unknown': c[40]['targets']['target_box_a'].update(component_present=False, contacts=None)
    elif defect == 'alias': c[40]['targets']['ground_plane']['collision_entity'] = 7
    elif defect == 'nan':
        c[40]['targets']['target_box_b']['contacts']['contact'][0]['wrench'][0]['body_1_wrench']['force']['z'] = 'NaN'
    elif defect == 'early_contact':
        value = deepcopy(c[530]['targets']['target_box_b']['contacts'])
        value['contact'][0]['collision1']['id'] = '7'
        c[530]['targets']['target_box_a']['contacts'] = value
    else:
        for physical, contact in zip(p[521:], c[521:]):
            physical['objects']['target_box_a']['pose'][2] = .1
            contact['targets']['target_box_a']['pose'][2] = .1
    with pytest.raises(ValueError): verify_evidence(p, c, 'target_box_a', lo, hi, d)
