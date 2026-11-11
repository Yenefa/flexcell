"""The pairing artefact must not manufacture a pairing it cannot justify.

WHY THE PAIRING IS THE DANGEROUS PART
    Capturing a frame is mechanical. Claiming that a frame was taken at a
    moment when the objects were at known poses is a factual claim, and it is
    the claim a later visual judgement will rest on. So the rules tested here
    are about what the tool REFUSES to assert:

      * a frame with no truth within the limit is unpaired, with a reason;
      * an object that was not measured is absent, never defaulted;
      * the gap between frame and truth is recorded, not smoothed away;
      * a pairing file that is all nulls still exits non-zero.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (ROOT.parent / 'ci-public-window' / 'scripts' /
          'evobot_visual_vs_truth.py')


def module():
    spec = importlib.util.spec_from_file_location('evobot_visual_vs_truth', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules['evobot_visual_vs_truth'] = loaded
    spec.loader.exec_module(loaded)
    return loaded


m = module()

FRAME = dict(path='/tmp/a.png', label='task_start', sha256='a' * 64,
             png_bytes=1234, width=640, height=480, stamp_ns=10 ** 9,
             captured_wall_ns=1_000_000_000)


def sample(wall_ns, objects=None):
    return dict(wall_ns=wall_ns, source='GZ_GROUND_TRUTH',
                objects=objects if objects is not None
                else {'target_box_a': [0.22, 0.0, 0.0175]})


# --------------------------------------------------------------- the pairing
def test_the_closest_truth_sample_wins_and_its_gap_is_recorded():
    samples = [sample(900_000_000), sample(1_050_000_000),
               sample(1_400_000_000)]
    pairing, reason = m.pair_one(FRAME, samples, max_gap_s=1.0)
    assert reason is None
    assert pairing['truth_wall_ns'] == 1_050_000_000
    assert pairing['pairing_gap_s'] == pytest.approx(0.05)


def test_truth_from_too_far_away_is_refused_not_annotated():
    """A pose from another moment does not describe this frame."""
    pairing, reason = m.pair_one(FRAME, [sample(5_000_000_000)], max_gap_s=1.0)
    assert pairing is None
    assert '4.000s away' in reason and 'does not describe this frame' in reason


def test_no_truth_at_all_is_refused():
    pairing, reason = m.pair_one(FRAME, [], max_gap_s=1.0)
    assert pairing is None and reason == 'no truth samples were taken'


def test_a_sample_with_no_objects_is_refused():
    pairing, reason = m.pair_one(FRAME, [sample(1_000_000_000, objects={})])
    assert pairing is None and 'no objects' in reason


def test_a_frame_without_a_capture_time_cannot_be_paired():
    broken = dict(FRAME)
    broken.pop('captured_wall_ns')
    pairing, reason = m.pair_one(broken, [sample(1_000_000_000)])
    assert pairing is None and 'captured_wall_ns' in reason


def test_objects_that_were_not_measured_stay_absent():
    """Never defaulted, never carried over from another sample."""
    samples = [sample(1_000_000_000, {'target_box_a': [0.22, 0.0, 0.0175]})]
    pairing, _ = m.pair_one(FRAME, samples)
    assert set(pairing['objects']) == {'target_box_a'}
    assert 'target_box_b' not in pairing['objects']


def test_the_pairing_carries_the_frame_identity_so_it_can_be_rechecked():
    pairing, _ = m.pair_one(FRAME, [sample(1_000_000_000)])
    assert pairing['png_sha256'] == 'a' * 64
    assert pairing['sim_stamp_ns'] == 10 ** 9
    assert pairing['truth_source'] == 'GZ_GROUND_TRUTH'


# ---------------------------------------------------------------- the report
def test_the_report_states_its_own_scope_so_it_cannot_be_over_read():
    report = m.build_report([], [], 0, 1.0)
    assert report['record_kind'] == 'EVOBOT_VISUAL_TRUTH_PAIRING'
    scope = report['scope']
    assert 'does NOT' in scope
    assert 'recognised' in scope and 'can see' in scope


def test_the_report_is_valid_json_without_nan(tmp_path):
    report = m.build_report([], [], 0, 1.0)
    text = json.dumps(report, allow_nan=False)
    assert 'NaN' not in text


# ------------------------------------------------------------- exit behaviour
def _write_frames(tmp_path, count=1, with_sidecar=True, sidecar_ok=True):
    from PIL import Image
    directory = tmp_path / 'frames'
    directory.mkdir()
    for index in range(count):
        path = directory / ('f%d.png' % index)
        Image.new('RGB', (8, 6), (index * 10 + 5, 40, 60)).save(path)
        if with_sidecar:
            record = dict(FRAME, path=str(path), ok=sidecar_ok,
                          label='stage_%d' % index)
            (directory / ('f%d.png.json' % index)).write_text(
                json.dumps(record), encoding='utf-8')
    return directory


def test_no_frames_is_a_non_zero_exit(tmp_path, capsys):
    empty = tmp_path / 'empty'
    empty.mkdir()
    code = m.main(['--frames', str(empty), '--out', str(tmp_path / 'p.json'),
                   '--truth', str(tmp_path / 't.json')])
    assert code == m.EXIT_NO_FRAMES
    assert 'NO_FRAMES' in capsys.readouterr().err


def test_frames_without_sidecars_exit_non_zero(tmp_path, capsys):
    frames = _write_frames(tmp_path, count=2, with_sidecar=False)
    truth = tmp_path / 't.json'
    truth.write_text(json.dumps([sample(1_000_000_000)]), encoding='utf-8')
    code = m.main(['--frames', str(frames), '--out', str(tmp_path / 'p.json'),
                   '--truth', str(truth)])
    assert code == m.EXIT_UNPAIRED
    report = json.loads((tmp_path / 'p.json').read_text())
    assert report['frames_paired'] == 0 and report['frames_unpaired'] == 2
    assert all('sidecar missing' in u['reason'] for u in report['unpaired'])


def test_a_failed_capture_sidecar_is_not_treated_as_a_frame(tmp_path):
    frames = _write_frames(tmp_path, count=1, sidecar_ok=False)
    truth = tmp_path / 't.json'
    truth.write_text(json.dumps([sample(1_000_000_000)]), encoding='utf-8')
    code = m.main(['--frames', str(frames), '--out', str(tmp_path / 'p.json'),
                   '--truth', str(truth)])
    assert code == m.EXIT_UNPAIRED


def test_a_successful_pairing_exits_zero(tmp_path):
    frames = _write_frames(tmp_path, count=1)
    truth = tmp_path / 't.json'
    truth.write_text(json.dumps([sample(1_000_000_000)]), encoding='utf-8')
    code = m.main(['--frames', str(frames), '--out', str(tmp_path / 'p.json'),
                   '--truth', str(truth)])
    assert code == m.EXIT_OK
    report = json.loads((tmp_path / 'p.json').read_text())
    assert report['frames_paired'] == 1 and report['frames_unpaired'] == 0


def test_existing_pairing_is_never_overwritten_without_force(tmp_path):
    frames = _write_frames(tmp_path, count=1)
    truth = tmp_path / 't.json'
    truth.write_text(json.dumps([sample(1_000_000_000)]), encoding='utf-8')
    out = tmp_path / 'p.json'
    out.write_text('{"keep": true}', encoding='utf-8')
    code = m.main(['--frames', str(frames), '--out', str(out),
                   '--truth', str(truth)])
    assert code == m.EXIT_USAGE
    assert json.loads(out.read_text()) == {'keep': True}


def test_truth_carried_in_the_sidecar_is_preferred(tmp_path):
    """The snapshot tool samples truth right after the frame; that gap is the
    real one, so it must win over an external sample taken later."""
    frames = _write_frames(tmp_path, count=1)
    sidecar = next(frames.glob('*.png.json'))
    record = json.loads(sidecar.read_text())
    record['truth'] = dict(available=True, wall_ns=1_000_000_100,
                           source='GZ_GROUND_TRUTH',
                           objects={'target_box_a': [0.11, -0.15, 0.0175]})
    sidecar.write_text(json.dumps(record), encoding='utf-8')
    truth = tmp_path / 't.json'
    truth.write_text(json.dumps([sample(1_000_000_000,
                                        {'target_box_a': [9.0, 9.0, 9.0]})]),
                     encoding='utf-8')
    code = m.main(['--frames', str(frames), '--out', str(tmp_path / 'p.json'),
                   '--truth', str(truth)])
    assert code == m.EXIT_OK
    pair = json.loads((tmp_path / 'p.json').read_text())['pairs'][0]
    # The sidecar's pose, not the external file's.
    assert pair['objects']['target_box_a'] == [0.11, -0.15, 0.0175]
    assert pair['pairing_gap_s'] < 0.001


def test_sidecar_truth_without_available_flag_is_not_used(tmp_path):
    frames = _write_frames(tmp_path, count=1)
    sidecar = next(frames.glob('*.png.json'))
    record = json.loads(sidecar.read_text())
    record['truth'] = dict(available=False, wall_ns=1, objects={},
                           error='sampler unavailable')
    sidecar.write_text(json.dumps(record), encoding='utf-8')
    code = m.main(['--frames', str(frames), '--out', str(tmp_path / 'p.json')])
    assert code == m.EXIT_USAGE


def test_live_truth_is_refused_when_no_objects_are_named(tmp_path, capsys):
    """The tool will not pair with truth it never measured."""
    frames = _write_frames(tmp_path, count=1)
    code = m.main(['--frames', str(frames), '--out', str(tmp_path / 'p.json')])
    assert code == m.EXIT_USAGE
    assert 'never measured' in capsys.readouterr().err
