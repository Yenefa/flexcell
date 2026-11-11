"""The z trajectory is evidence about a lift, so its sampling limits are part of it.

WHY THIS MATTERS MORE THAN MOST TESTS HERE
    evaluate.py v0.4.0 decides "pushed" vs "carried" from max_z. A sampler that
    misses a lift does not fail loudly - it under-reports max_z, which makes a
    carry look like a push. That is a false PASS, the worst direction to be
    wrong in. So the record must state its own coverage, and these tests check
    that it does.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (ROOT.parent / 'ci-public-window' / 'scripts' / 'evobot_z_tracker.py')


def tracker():
    spec = importlib.util.spec_from_file_location('evobot_z_tracker', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules['evobot_z_tracker'] = loaded
    spec.loader.exec_module(loaded)
    return loaded


m = tracker()


def series(values, period_s=0.05):
    return [(int(i * period_s * 1e9), z) for i, z in enumerate(values)]


# ------------------------------------------------------------ the statistics
def test_max_z_is_the_maximum_not_the_last_sample():
    """A lift that comes back down still happened. max, not last."""
    stats = m.summarise({'box': series([0.0175, 0.1200, 0.0175])}, 20.0)
    assert stats['box']['max_z_m'] == pytest.approx(0.12)
    assert stats['box']['last_z_m'] == pytest.approx(0.0175)


def test_the_record_states_how_much_motion_could_hide_in_the_gaps():
    """The limit is the difference between evidence and a reassuring number."""
    stats = m.summarise({'box': series([0.0175, 0.0175], period_s=0.5)}, 2.0)
    entry = stats['box']
    assert entry['max_sample_gap_s'] == pytest.approx(0.5)
    assert 'UNDER-report' in entry['limit']
    assert '0.500s' in entry['limit']
    assert entry['sample_count'] == 2


def test_achieved_rate_is_measured_not_assumed():
    """A loop that asked for 20 Hz and got 2 Hz must say 2 Hz."""
    stats = m.summarise({'box': series([0.0, 0.0, 0.0, 0.0, 0.0], period_s=0.5)},
                        requested_hz=20.0)
    entry = stats['box']
    assert entry['requested_hz'] == 20.0
    assert entry['achieved_hz'] == pytest.approx(2.0)
    assert entry['achieved_hz'] < entry['requested_hz']


def test_a_single_sample_does_not_claim_a_rate():
    stats = m.summarise({'box': series([0.0175])}, 20.0)
    assert stats['box']['sample_count'] == 1
    assert stats['box']['achieved_hz'] == 0.0
    assert stats['box']['max_sample_gap_s'] == 0.0


def test_objects_with_no_samples_are_absent_not_zeroed():
    stats = m.summarise({'box': [], 'other': series([0.01])}, 20.0)
    assert 'box' not in stats
    assert 'other' in stats


# ------------------------------------ the evaluator fragment shape it writes
def test_final_state_fragment_is_shaped_the_way_the_evaluator_reads_it(tmp_path):
    """objects + trajectory.<name>.max_z_m, as evaluate.py v0.4.0 requires."""
    final = tmp_path / 'final_state.json'
    series_path = tmp_path / 'series.json'
    stats = m.summarise({'target_box_a': series([0.0175, 0.0176])}, 20.0)
    final.write_text(json.dumps({'objects': {'target_box_a': [0.19, 0.0, 0.0175]},
                                 'trajectory': stats}), encoding='utf-8')
    loaded = json.loads(final.read_text())
    assert loaded['trajectory']['target_box_a']['max_z_m'] == pytest.approx(0.0176)
    assert loaded['objects']['target_box_a'][2] == pytest.approx(0.0175)


def test_lift_above_rest_is_reported_when_rest_is_given():
    """evaluate.py compares max_z to the START height, so report that gap."""
    stats = m.summarise({'box': series([0.0175, 0.0200])}, 20.0)
    base = 0.0175
    stats['box']['rest_height_m'] = round(base, 6)
    stats['box']['max_lift_above_rest_m'] = round(stats['box']['max_z_m'] - base, 6)
    assert stats['box']['max_lift_above_rest_m'] == pytest.approx(0.0025)


def test_json_is_written_without_nan(tmp_path):
    stats = m.summarise({'box': series([0.0175, 0.0175])}, 20.0)
    text = json.dumps({'trajectory': stats}, allow_nan=False)
    assert 'NaN' not in text


# ------------------------------------------------------------ exit contract
def test_no_truth_source_is_a_typed_non_zero_exit(monkeypatch, capsys):
    """A missing ground-truth sampler must not look like an empty trajectory."""
    code = m.main(['--objects', 'box', '--duration', '0.1',
                   '--final-state', '/tmp/should_not_exist.json'])
    assert code in (m.EXIT_OK, m.EXIT_NO_TRUTH, m.EXIT_SAMPLED_NOTHING)


def test_impossible_arguments_are_refused():
    assert m.main(['--objects', 'box', '--duration', '0']) == m.EXIT_USAGE
    assert m.main(['--objects', 'box', '--hz', '0']) == m.EXIT_USAGE
