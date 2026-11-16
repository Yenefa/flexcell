"""Tests for the window aggregator (no ROS, no simulator)."""
import json
from pathlib import Path

import analyze_windows as aw


def make_slot(root, label, error_m, place_detail, verify_detail, targets):
    run = Path(root) / label / 'run-test'
    (run / 'skills').mkdir(parents=True)
    (run / 'result.json').write_text(json.dumps({
        'case': 'normal', 'status': 'PASS',
        'task': dict(outcome='OUTCOME_SUCCEEDED', error_code='ERR_NONE',
                     wall_seconds=14.0, final_position_error_m=error_m),
    }))
    (run / 'skills/place.jsonl').write_text(json.dumps({'detail': place_detail}) + '\n')
    (run / 'skills/verify.jsonl').write_text(json.dumps({'detail': verify_detail}) + '\n')
    (run / 'skills/move_to_pose.jsonl').write_text(
        ''.join(json.dumps({'target': {'position': list(t)}}) + '\n' for t in targets))


def test_parse_mm_extracts_metres_as_millimetres():
    assert aw.parse_mm('placed target_box_a: drop error 0.008m', 'drop error') == 8.0
    assert aw.parse_mm('measured within 0.060m of expected (err=0.0001)', 'err=') == 0.1


def test_parse_mm_returns_none_without_marker():
    assert aw.parse_mm('no measurement here', 'drop error') is None
    assert aw.parse_mm(None, 'err=') is None


def test_slot_row_reads_the_declared_fields(tmp_path):
    make_slot(tmp_path, 'NORMAL_1', 0.0076,
              'placed target_box_a: drop error 0.008m',
              'measured within 0.060m of expected (err=0.0076)',
              [(0.12, -0.15, 0.1895), (0.12, -0.15, 0.2895)])
    row = aw.slot_row(tmp_path, 'NORMAL_1')
    assert row['final_error_mm'] == 7.6
    assert row['place_drop_mm'] == 8.0
    assert row['verify_error_mm'] == 7.6
    assert row['last_targets'][0] == (0.12, -0.15, 0.1895)


def test_missing_slot_is_reported_not_crashing(tmp_path):
    row = aw.slot_row(tmp_path, 'NORMAL_1')
    assert row['missing'] is True


def test_summary_counts_completed_slots_and_spread(tmp_path):
    make_slot(tmp_path, 'NORMAL_1', 0.0076, 'drop error 0.008m', 'err=0.0076', [(0.12, -0.15, 0.1895)])
    make_slot(tmp_path, 'NORMAL_2', 0.0139, 'drop error 0.014m', 'err=0.0139', [(0.12, -0.15, 0.1895)])
    rows = [aw.slot_row(tmp_path, l) for l in ('NORMAL_1', 'NORMAL_2')]
    s = aw.summarize(rows)
    assert s['slots_completed'] == 2
    assert s['error_mm']['min'] == 7.6
    assert s['error_mm']['max'] == 13.9
    assert s['unique_release_target_sets'] == 1
    assert s['max_place_verify_delta_mm'] < 1.0


def test_summary_detects_two_distinct_target_sets(tmp_path):
    make_slot(tmp_path, 'NORMAL_1', 0.008, 'drop error 0.008m', 'err=0.008', [(0.12, -0.15, 0.1895)])
    make_slot(tmp_path, 'NORMAL_2', 0.008, 'drop error 0.008m', 'err=0.008', [(0.13, -0.15, 0.1895)])
    rows = [aw.slot_row(tmp_path, l) for l in ('NORMAL_1', 'NORMAL_2')]
    assert aw.summarize(rows)['unique_release_target_sets'] == 2
