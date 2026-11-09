"""Missing contact/force observations must never be mistaken for measured zero."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('contact_gate', ROOT / 'scripts/contact_gate.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def target():
    return dict(collision_entity=7, component_present=True, pose=[0., 0., .0175, 0., 0., 0., 1.],
        contacts={'contact': [dict(collision1={'id': '7'}, collision2={'id': '4'}, position=[{}],
            wrench=[dict(body_1_wrench={'force': {'z': .49}}, body_2_wrench={'force': {'z': -.49}})])]})


def fixture():
    declaration = dict(samples=12, step_ns=2_000_000, settle_from_ns=10_000_000,
        settle_to_ns=20_000_000, availability_from_ns=4_000_000, min_force_samples=6,
        force_mean_min_n=.392, force_mean_max_n=.588,
        targets=dict(positive='a', empty='b', missing='c'))
    rows = []
    for i in range(12):
        a = target(); b = deepcopy(a); b.update(collision_entity=8, contacts={})
        c = deepcopy(a); c.update(collision_entity=9, component_present=False, contacts=None)
        rows.append(dict(schema_version=1, source='ECM_POST_PHYSICS', sim_ns=(i+1)*2_000_000,
                         step_ns=2_000_000, monotonic_ns=i+1, targets=dict(a=a, b=b, c=c)))
    return rows, declaration


def test_real_zero_empty_set_and_missing_component_are_distinct():
    value = target()
    assert gate.observation(value)['force_magnitude_n'] == .49
    for wrench in value['contacts']['contact'][0]['wrench']:
        wrench['body_1_wrench']['force'] = wrench['body_2_wrench']['force'] = {}
    assert gate.observation(value)['force_magnitude_n'] == 0.
    value['contacts'] = {}
    assert gate.observation(value) == dict(state='NO_REPORTED_CONTACTS', force_magnitude_n=None, contacts=0)
    value.update(component_present=False, contacts=None)
    assert gate.observation(value) == dict(state='UNKNOWN', force_magnitude_n=None, contacts=None)


@pytest.mark.parametrize('missing', ['wrench', 'body', 'force'])
def test_contact_without_force_is_unknown_instead_of_zero(missing):
    value = target(); contact = value['contacts']['contact'][0]
    if missing == 'wrench': contact['wrench'] = []
    elif missing == 'body': contact['wrench'][0].pop('body_1_wrench')
    else: contact['wrench'][0]['body_1_wrench'].pop('force')
    observed = gate.observation(value)
    assert observed['state'] == 'CONTACTS_FORCE_UNKNOWN' and observed['force_magnitude_n'] is None


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', float('nan'), None, True])
def test_nonfinite_proto_json_force_is_rejected(bad):
    value = target(); value['contacts']['contact'][0]['wrench'][0]['body_1_wrench']['force']['z'] = bad
    with pytest.raises(ValueError): gate.observation(value)


@pytest.mark.parametrize('defect', ['other_collision', 'unbalanced'])
def test_identity_and_raw_bilateral_force_consistency_are_checked(defect):
    value = target(); contact = value['contacts']['contact'][0]
    if defect == 'other_collision': contact['collision1']['id'] = '99'
    else: contact['wrench'][0]['body_2_wrench']['force']['z'] = .49
    with pytest.raises(ValueError): gate.observation(value)


def test_full_fixed_window_keeps_unknown_control_and_measured_weight_separate():
    rows, declaration = fixture()
    result = gate.verify_rows(rows, declaration)
    assert result['status'] == 'CONTACT_PIPELINE_PASS' and result['mean_force_magnitude_n'] == .49
    assert result['states']['c'] == {'UNKNOWN': 12} and result['default_admission'] == 'NO_GO'


@pytest.mark.parametrize('defect', ['missing_step', 'clock_reversed', 'unknown_as_zero', 'empty_positive', 'false_zero', 'nan_before_settle', 'aliased_control'])
def test_corrupt_or_unobserved_window_cannot_pass(defect):
    rows, declaration = fixture()
    if defect == 'missing_step': rows.pop()
    elif defect == 'clock_reversed': rows[3]['sim_ns'] = rows[2]['sim_ns']
    elif defect == 'unknown_as_zero': rows[3]['targets']['c'].update(component_present=True, contacts={})
    elif defect == 'empty_positive':
        for row in rows: row['targets']['a']['contacts'] = {}
    elif defect == 'false_zero':
        for row in rows:
            for wrench in row['targets']['a']['contacts']['contact'][0]['wrench']:
                wrench['body_1_wrench']['force'] = wrench['body_2_wrench']['force'] = {}
    elif defect == 'aliased_control': rows[3]['targets']['c']['collision_entity'] = 7
    else:
        rows[0]['targets']['a']['contacts']['contact'][0]['wrench'][0]['body_1_wrench']['force']['z'] = 'NaN'
    with pytest.raises(ValueError): gate.verify_rows(rows, declaration)


def test_world_mismatch_is_retained_without_starting_simulator(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('contact_probe', ROOT / 'scripts/contact_probe.py')
    probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)
    (tmp_path / 'world.sdf').write_text('<sdf/>')
    declaration = json.loads((ROOT / 'infra/contact-probe.json').read_text())
    declaration.update(world='world.sdf', world_sha256='0' * 64)
    manifest = tmp_path / 'declaration.json'; manifest.write_text(json.dumps(declaration))
    out = tmp_path / 'result'
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    launched = Mock(); monkeypatch.setattr(probe.subprocess, 'Popen', launched)
    monkeypatch.setattr(sys, 'argv', ['contact_probe', '--out', str(out), '--declaration', str(manifest)])
    assert probe.main() == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'STOPPED' and result['logical_robot_tasks'] == 0
    assert 'world differs' in result['error'] and result['no_replacements'] is True
    launched.assert_not_called()
