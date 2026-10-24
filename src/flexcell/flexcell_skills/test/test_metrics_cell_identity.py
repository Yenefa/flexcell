"""Exercise report cell assignment without ROS, a model, or robot execution."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    'metrics_report_cell_identity', ROOT / 'setup' / '95_metrics_report.py')
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
S4_ARCHIVE = (ROOT / 'setup' / 'acceptance' / 'm3_online_v2_20260930' /
              'fsm_s3_s4' / 'episodes' /
              'pick_place_v1_pick_place_v1-16d5aa87.json')


def write_batch(path, episode):
    path.write_text(json.dumps({'scenario': 'S4', 'episode': str(episode)}) + '\n',
                    encoding='utf-8')


@pytest.mark.parametrize('outcome', ['0', '1'])
def test_unlabelled_single_object_outcomes_do_not_imply_s4(tmp_path, outcome):
    episode = tmp_path / 'single.json'
    episode.write_text(json.dumps({
        'scenario_id': 'pick_place_v1', 'policy': {'name': 'fsm'},
        'final_state': {'outcome': outcome}, 'steps': [],
    }), encoding='utf-8')

    loaded = REPORT.load_episodes(str(tmp_path), None)

    assert len(loaded) == 1
    assert REPORT.cell_of(loaded[0][1]).startswith('dev/pick_place_v1 @ ')


def test_batch_labels_only_its_episode_in_memory(tmp_path):
    store = tmp_path / 'episodes'
    store.mkdir()
    ordinary = store / 'ordinary.json'
    ordinary.write_text(json.dumps({
        'scenario_id': 'pick_place_v1', 'policy': {'name': 'fsm'},
        'final_state': {'outcome': '0'}, 'steps': [],
    }), encoding='utf-8')
    s4 = store / 's4.json'
    s4.write_bytes(S4_ARCHIVE.read_bytes())
    original = {path: path.read_bytes() for path in (ordinary, s4)}
    batch = tmp_path / 'batch.jsonl'
    write_batch(batch, s4)

    selected = REPORT.load_episodes(str(store), str(batch))

    assert [path for path, _ in selected] == [str(s4)]
    assert selected[0][1]['scenario_id'] == 'pick_place_v1'
    assert REPORT.cell_of(selected[0][1]).startswith('S4 @ ')
    assert 'benchmark_cell' not in json.loads(s4.read_bytes())
    unlabelled = REPORT.load_episodes(str(store), None)
    assert len(unlabelled) == 2
    assert all(REPORT.cell_of(record).startswith('dev/pick_place_v1 @ ')
               for _, record in unlabelled)
    assert {path: path.read_bytes() for path in original} == original


def test_batch_report_keeps_s4_cell_when_historical_replay_diverges(tmp_path):
    s4 = tmp_path / 's4.json'
    original = S4_ARCHIVE.read_bytes()
    s4.write_bytes(original)
    batch = tmp_path / 'batch.jsonl'
    write_batch(batch, s4)
    selected = REPORT.load_episodes(str(tmp_path), str(batch))

    cells, problems = REPORT.episode_rows(selected)
    text, verdict = REPORT.report(selected, min_cell=1)

    assert not problems
    assert len(cells) == 1
    cell, rows = next(iter(cells.items()))
    assert cell.startswith('S4 @ ')
    assert len(rows) == 1
    assert rows[0]['outcome'] == '1'
    # The current FSM added ERR_MOTION_FAILED to the ABORT explanation.
    # Strict replay compares the complete decision, including that text.
    assert rows[0]['replay_ok'] is False
    assert rows[0]['replayed_n'] == 4
    assert rows[0]['replay_diverged_steps'] == 1
    assert verdict == 'FAIL'
    assert '## Cell S4 ' in text
    assert '| success rate (metric 1) | 0/1' in text
    assert '| replay integrity | 0/1 replayed episodes clean' in text
    assert '**REPLAY-DIRTY**' in text
    assert s4.read_bytes() == original


def test_same_s4_episode_without_batch_is_reported_as_dev(tmp_path):
    s4 = tmp_path / 's4.json'
    s4.write_bytes(S4_ARCHIVE.read_bytes())

    text, verdict = REPORT.report(
        REPORT.load_episodes(str(tmp_path), None), min_cell=1)

    assert verdict == 'FAIL'
    assert '## Cell dev/pick_place_v1 ' in text
    assert '## Cell S4 ' not in text
