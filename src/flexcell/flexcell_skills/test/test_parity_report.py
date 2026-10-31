"""Parity is the same manifest, the same declared tolerance, the same criterion."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from parity_report import compare

CASES = [('normal', 'target_box_a'), ('normal', 'target_box_b'), ('dual_object', 'target_box_a'),
         ('recovery_once', 'target_box_a'), ('budget_exhaustion', 'target_box_a')]


def run_dir(root, backend, index, *, error_m=.0002, tolerance_m=.06, picks=1):
    run = root / ('parity-' + backend) / ('run-%s-%d' % (backend, index))
    skills = run / 'skills'
    skills.mkdir(parents=True)
    (skills / 'verify.jsonl').write_text(json.dumps(dict(
        object_name='target_box_a', position_error_m=error_m, tolerance_m=tolerance_m,
        measured=[.12, -.15, .0175], expected=[.12, -.15, .0175])) + '\n')
    (skills / 'pick.jsonl').write_text(''.join(
        json.dumps(dict(object_name='target_box_a', outcome='0')) + '\n' for _ in range(picks)))
    (skills / 'place.jsonl').write_text(json.dumps(dict(outcome='0')) + '\n')
    return run


def window(root, backend, *, digest='d' * 64, failing_case=None, error_m=.0002, picks=1):
    out = root / ('parity-' + backend)
    out.mkdir(parents=True, exist_ok=True)
    episodes = []
    for index, (case, obj) in enumerate(CASES):
        run = run_dir(root, backend, index, error_m=error_m, picks=picks)
        status = 'STOPPED' if failing_case == case else 'PASS'
        episodes.append(dict(
            case=case, object=obj, run=str(run),
            result=dict(status=status, expectation_met=status == 'PASS',
                        task=dict(outcome='OUTCOME_SUCCEEDED', final_position_error_m=None))))
    data = dict(schema_version=1, status='FUNCTIONAL_WINDOW_PASS', declaration_sha256=digest,
                backend=backend, episodes=episodes)
    (out / 'window.json').write_text(json.dumps(data))
    return out / 'window.json'


def test_three_backends_on_the_same_manifest_pass(tmp_path):
    paths = [window(tmp_path, name) for name in ('teleport', 'velocity', 'joint')]
    report = compare(paths)
    assert report['status'] == 'CARRY_BACKEND_PARITY_PASS'
    assert report['tolerance_moved'] is False
    assert report['declared_tolerance_m'] == .06
    assert report['max_verified_error_m'] == {name: .0002 for name in report['table']}
    assert report['attempts']['parity-joint']['normal'] == 1


def test_the_verifiers_own_error_is_reported_not_just_the_verdict(tmp_path):
    paths = [window(tmp_path, 'teleport', error_m=.0002),
             window(tmp_path, 'joint', error_m=.0123)]
    report = compare(paths)
    assert report['max_verified_error_m']['parity-joint'] == pytest.approx(.0123)
    assert report['max_verified_error_m']['parity-teleport'] == pytest.approx(.0002)
    joint = [row for row in report['table']['parity-joint']['cases'] if row['case'] == 'normal']
    assert joint[0]['verify_error_m'] == pytest.approx(.0123)


def test_an_error_over_the_declared_tolerance_breaks_parity(tmp_path):
    paths = [window(tmp_path, 'teleport'), window(tmp_path, 'joint', error_m=.07)]
    with pytest.raises(ValueError, match='exceeds the declared'):
        compare(paths)


def test_windows_from_different_manifests_are_not_compared(tmp_path):
    paths = [window(tmp_path, 'teleport'), window(tmp_path, 'joint', digest='e' * 64)]
    with pytest.raises(ValueError, match='same manifest'):
        compare(paths)


def test_a_failed_case_breaks_parity(tmp_path):
    paths = [window(tmp_path, 'teleport'), window(tmp_path, 'joint', failing_case='dual_object')]
    with pytest.raises(ValueError, match='parity broken'):
        compare(paths)


def test_a_short_window_is_not_parity(tmp_path):
    path = window(tmp_path, 'teleport')
    data = json.loads(path.read_text())
    data['episodes'] = data['episodes'][:4]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='declared number of cases'):
        compare([path, window(tmp_path, 'joint')])
