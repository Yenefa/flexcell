"""Parity is the same manifest and the same criterion on every backend."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from parity_report import compare

CASES = [('normal', 'target_box_a'), ('normal', 'target_box_b'), ('dual_object', 'target_box_a'),
         ('recovery_once', 'target_box_a'), ('budget_exhaustion', 'target_box_a')]


def window(root, backend, *, digest='d' * 64, status='FUNCTIONAL_WINDOW_PASS',
           failing_case=None, placement=(.004, .004, .004, .004, .004)):
    out = root / ('parity-' + backend)
    out.mkdir(parents=True)
    episodes = []
    for index, (case, obj) in enumerate(CASES):
        case_status = 'STOPPED' if failing_case == case and backend == 'joint' else 'PASS'
        episodes.append(dict(
            case=case, object=obj,
            result=dict(status=case_status, expectation_met=case_status == 'PASS',
                        task=dict(outcome='OUTCOME_SUCCEEDED', error_code=None,
                                  final_position_error_m=placement[index]))))
    window = dict(schema_version=1, status=status, declaration_sha256=digest,
                  backend=backend, episodes=episodes)
    (out / 'window.json').write_text(json.dumps(window))
    return out / 'window.json'


def test_three_backends_on_the_same_manifest_pass(tmp_path):
    paths = [window(tmp_path, name) for name in ('teleport', 'velocity', 'joint')]
    report = compare(paths)
    assert report['status'] == 'CARRY_BACKEND_PARITY_PASS'
    assert report['tolerance_moved'] is False
    assert report['max_placement_error_m'] == .012
    assert list(report['table']) == ['parity-teleport', 'parity-velocity', 'parity-joint']


def test_windows_from_different_manifests_are_not_compared(tmp_path):
    paths = [window(tmp_path, 'teleport'), window(tmp_path, 'joint', digest='e' * 64)]
    with pytest.raises(ValueError, match='same manifest'):
        compare(paths)


def test_a_failed_case_breaks_parity(tmp_path):
    paths = [window(tmp_path, 'teleport'), window(tmp_path, 'joint', failing_case='dual_object')]
    with pytest.raises(ValueError, match='parity broken'):
        compare(paths)


def test_a_placement_outside_the_tolerance_breaks_parity(tmp_path):
    paths = [window(tmp_path, 'teleport'),
             window(tmp_path, 'joint', placement=(.004, .004, .02, .004, .004))]
    with pytest.raises(ValueError, match='placement error'):
        compare(paths)


def test_a_short_window_is_not_parity(tmp_path):
    path = window(tmp_path, 'teleport')
    data = json.loads(path.read_text())
    data['episodes'] = data['episodes'][:4]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='declared number of cases'):
        compare([path, window(tmp_path, 'joint')])
