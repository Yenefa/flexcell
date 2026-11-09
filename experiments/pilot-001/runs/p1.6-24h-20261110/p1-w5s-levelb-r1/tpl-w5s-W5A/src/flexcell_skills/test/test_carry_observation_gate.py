"""Adversarial segment receipts for #32; no ROS, network or robot commands."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'setup/112_carry_observation_gate.py'
spec = importlib.util.spec_from_file_location('carry_observation_gate', SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def reset():
    return dict(ok=True, rc=0, report=dict(ok=True, report=dict(
        task_idle=True, task_state_seen='IDLE', carry_disengaged=True)))


def action(success=True, token='b' * 32):
    return dict(accepted=True, terminal_confirmed=True, harness_error=None,
                ros_status=4 if success else 6, goal_uuid=token)


def fixture(failed=False):
    session, obj, ev = 'a' * 32, 'target_box_a', 'pick-evidence-1'
    before, after = [.22, 0., .0175], [.22, 0., .016 if failed else .11]
    rise = after[2] - before[2]
    probe = dict(trial=1, object_name=obj, harness_error=None,
                 precondition=dict(ok=True, reset=reset(), injection_clear=dict(rc=0)),
                 cleanup=reset(), action=action(not failed), pick_ok=not failed,
                 outcome=1 if failed else 0, status=2 if failed else 1,
                 error_code=23 if failed else 0, grasp_attached=not failed,
                 evidence_id=ev, before=before, after=after, rise_m=rise)
    if not failed:
        probe['release'] = dict(action(token='c' * 32), outcome=0, status=1, error_code=0,
                                released=True, evidence_id='place-evidence-1', measured_after=before)
    pick = dict(evidence_id=ev, object_name=obj, profile='demo_slow',
                outcome=str(probe['outcome']), status=probe['status'], error_code=probe['error_code'],
                box_before=before, box_after=after, box_rise_m=rise,
                attach_gap_m=.16, carry_offset=[0., 0., -.16], wall_ts=110., elapsed_ms=10000)
    def summary(wall, n, missing, confirmed, final=False):
        return dict(event='teleport_loop_summary', schema_version=1, session=session,
                    object=obj, backend='teleport', wall_ts=wall, final=final,
                    started_mono_ns=100_000_000_000,
                    sample_mono_ns=100_000_000_000 + int((wall - 104) * 1e9), period_s=.1,
                    ee_lookup_count=n, ee_missing_count=missing,
                    ee_missing_streak=0, ee_missing_streak_max=1,
                    ee_lookup_ns_total=500_000_000 * missing, ee_lookup_ns_max=500_000_000,
                    pin_requests=n - missing, pin_confirmed=confirmed,
                    pin_failed=n - missing - confirmed, pin_skipped_no_offset=0)
    final_wall = 109. if failed else 115.
    carry = [dict(event='start', object=obj, session=session, backend='teleport',
                  offset=[0., 0., -.16], wall_ts=104.),
             summary(105., 5, 2, 3), summary(108., 10, 3, 5),
             summary(final_wall, 20, 4, 14, True),
             dict(event='stop', object=obj, session=session, backend='teleport',
                  engaged=True, cause='release', wall_ts=final_wall + .1)]
    return [probe], [pick], carry


def audit(data, segment='A1', rc=0):
    return gate.audit_segment(segment, *data, rc)


def test_success_prefix_excludes_place_and_keeps_the_real_denominators():
    report = audit(fixture())
    assert report['status'] == 'SEGMENT_EVIDENCE_COMPLETE'
    trial = report['trials'][0]
    assert trial['pick_prefix']['ee_lookup_count'] == 10
    assert trial['pick_prefix']['ee_missing_fraction'] == .3
    assert trial['session_totals']['ee_lookup_count'] == 20
    assert trial['session_totals']['ee_missing_fraction'] == .2
    assert trial['pick_prefix_age_s'] == 2.
    assert trial['association'] == 'OBJECT_TIME_UNIQUE_NOT_GOAL_UUID'
    assert report['root_cause'] == 'UNKNOWN'


def test_measured_physical_failure_is_complete_evidence_and_is_never_replaced():
    report = audit(fixture(failed=True))
    assert not report['errors'] and report['observed_trials'] == 1
    assert report['trials'][0]['pick_ok'] is False
    assert report['trials'][0]['rise_m'] < 0
    assert report['trials'][0]['pick_prefix'] == report['trials'][0]['session_totals']


def test_all_missing_lookups_is_an_observation_without_inventing_pin_failures():
    data = fixture(failed=True)
    for row in data[2][1:-1]:
        row.update(ee_missing_count=row['ee_lookup_count'], ee_missing_streak=row['ee_lookup_count'],
                   ee_missing_streak_max=row['ee_lookup_count'],
                   pin_requests=0, pin_confirmed=0, pin_failed=0)
    report = audit(data)
    assert not report['errors']
    assert report['trials'][0]['session_totals']['ee_missing_fraction'] == 1.
    assert report['trials'][0]['session_totals']['pin_failed'] == 0


@pytest.mark.parametrize('defect', [
    'missing_final', 'duplicate_final', 'after_final', 'missing_summaries',
    'bad_schema', 'wrong_object', 'wrong_backend', 'changed_start', 'changed_period',
    'reversed_time', 'too_frequent', 'boolean_counter', 'negative_counter',
    'lookup_partition', 'pin_partition', 'bad_streak', 'bad_duration',
    'decreased_counters', 'no_pick_prefix', 'missing_stop', 'ambiguous_stop',
    'wrong_stop_object', 'stop_before_final', 'ambiguous_start', 'reused_session_start',
    'wrong_offset', 'wrong_stage_result', 'wrong_pose', 'wrong_rise', 'injected',
    'harness_error', 'unknown_terminal', 'cancel_ack_only', 'failed_cleanup',
    'unknown_idle', 'unknown_carry', 'failed_precondition', 'failed_clear',
    'unconfirmed_release', 'release_harness_error', 'missing_goal', 'boolean_trial',
])
def test_defects_cannot_turn_into_permission_to_continue(defect):
    data = fixture()
    p, pick, carry = data[0][0], data[1][0], data[2]
    if defect == 'missing_final': carry.pop(-2)
    elif defect == 'duplicate_final': carry.insert(-1, deepcopy(carry[-2]))
    elif defect == 'after_final': carry.insert(-1, deepcopy(carry[1]))
    elif defect == 'missing_summaries': carry[:] = [carry[0], carry[-1]]
    elif defect == 'bad_schema': carry[1]['schema_version'] = 2
    elif defect == 'wrong_object': carry[1]['object'] = 'target_box_b'
    elif defect == 'wrong_backend': carry[1]['backend'] = 'velocity_servo'
    elif defect == 'changed_start': carry[2]['started_mono_ns'] -= 1
    elif defect == 'changed_period': carry[2]['period_s'] = .2
    elif defect == 'reversed_time': carry[2]['wall_ts'] = 104.
    elif defect == 'too_frequent': carry[2]['sample_mono_ns'] = carry[1]['sample_mono_ns'] + 1
    elif defect == 'boolean_counter': carry[1]['pin_failed'] = False
    elif defect == 'negative_counter': carry[1]['pin_failed'] = -1
    elif defect == 'lookup_partition': carry[1]['ee_lookup_count'] += 1
    elif defect == 'pin_partition': carry[1]['pin_failed'] += 1
    elif defect == 'bad_streak': carry[1]['ee_missing_streak_max'] = 3
    elif defect == 'bad_duration': carry[1]['ee_lookup_ns_max'] = 2_000_000_000
    elif defect == 'decreased_counters': carry[2] = dict(carry[1], wall_ts=108., sample_mono_ns=104_000_000_000, ee_lookup_ns_max=400_000_000)
    elif defect == 'no_pick_prefix': carry[:] = [carry[0], carry[-2], carry[-1]]
    elif defect == 'missing_stop': carry.pop()
    elif defect == 'ambiguous_stop': carry.append(deepcopy(carry[-1]))
    elif defect == 'wrong_stop_object': carry[-1]['object'] = 'target_box_b'
    elif defect == 'stop_before_final': carry[-1]['wall_ts'] = 114.
    elif defect == 'ambiguous_start': carry.insert(1, dict(carry[0], session='d' * 32))
    elif defect == 'reused_session_start': carry.insert(0, dict(carry[0], wall_ts=50.))
    elif defect == 'wrong_offset': carry[0]['offset'][2] = -.1
    elif defect == 'wrong_stage_result': pick['outcome'] = '1'
    elif defect == 'wrong_pose': pick['box_before'] = [0., 0., 0.]
    elif defect == 'wrong_rise': pick['box_rise_m'] = -.1
    elif defect == 'injected': pick['injected'] = True
    elif defect == 'harness_error': p['harness_error'] = 'timeout'
    elif defect == 'unknown_terminal': p['action']['terminal_confirmed'] = False
    elif defect == 'cancel_ack_only': p['action'].update(terminal_confirmed=False, cancel_acknowledged=True)
    elif defect == 'failed_cleanup': p['cleanup']['rc'] = 139
    elif defect == 'unknown_idle': p['cleanup']['report']['report']['task_state_seen'] = 'UNAVAILABLE'
    elif defect == 'unknown_carry': p['cleanup']['report']['report']['carry_disengaged'] = None
    elif defect == 'failed_precondition': p['precondition']['ok'] = False
    elif defect == 'failed_clear': p['precondition']['injection_clear']['rc'] = 1
    elif defect == 'unconfirmed_release': p['release']['released'] = False
    elif defect == 'release_harness_error': p['release']['harness_error'] = 'result timeout'
    elif defect == 'missing_goal': p['action']['goal_uuid'] = None
    elif defect == 'boolean_trial': p['trial'] = True
    assert audit(data)['status'] == 'STOP_INCOMPLETE_EVIDENCE', defect


@pytest.mark.parametrize('extra', [False, True])
def test_missing_or_extra_trial_cannot_refill_a_segment(extra):
    data = fixture()
    if extra:
        data[0].append(deepcopy(data[0][0]))
    else:
        data[0].clear()
    assert audit(data)['errors']


def test_duplicate_pick_evidence_is_ambiguous_even_when_payloads_are_identical():
    data = fixture()
    data[1].append(deepcopy(data[1][0]))
    assert 'AMBIGUOUS' in audit(data)['errors'][0]


def test_nonzero_process_receipt_blocks_complete_physical_results():
    assert audit(fixture(), rc=139)['status'] == 'STOP_INCOMPLETE_EVIDENCE'


@pytest.mark.parametrize('segment,count,object_name', [('A4', 4, 'target_box_a'), ('B5', 5, 'target_box_b')])
def test_all_prescribed_trials_need_distinct_evidence_goals_and_sessions(segment, count, object_name):
    probes, picks, carry = [], [], []
    for i in range(count):
        data = fixture(failed=i == 0)
        p, pick = data[0][0], data[1][0]
        p.update(trial=i + 1, object_name=object_name, evidence_id='ev-%d' % i)
        p['action']['goal_uuid'] = '%032x' % (i + 100)
        pick.update(object_name=object_name, evidence_id=p['evidence_id'], wall_ts=110. + i * 50)
        for row in data[2]:
            row.update(object=object_name, session='%032x' % i, wall_ts=row['wall_ts'] + i * 50)
        probes.append(p)
        picks.append(pick)
        carry.extend(data[2])
    assert not audit((probes, picks, carry), segment)['errors']
    probes[-1]['action']['goal_uuid'] = probes[0]['action']['goal_uuid']
    assert 'reused goal_uuid' in audit((probes, picks, carry), segment)['errors'][-1]


@pytest.mark.parametrize('bad', ['{"x":1,"x":2}\n', '{"x":NaN}\n', '{"x":Infinity}\n',
                              '{"x":1e999}\n', '[]\n', '{"unfinished":', '\0{}\n'])
def test_malformed_fresh_logs_are_rejected_without_sanitizing(tmp_path, bad):
    path = tmp_path / 'carry.jsonl'
    path.write_text(bad)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        gate.read_input(path)
    assert path.read_bytes() == before


def test_explicit_byte_offset_preserves_a_legacy_prefix_and_hashes_the_whole_snapshot(tmp_path):
    path = tmp_path / 'carry.jsonl'
    prefix = b'\0historical broken row\n'
    path.write_bytes(prefix + b'{"new":true}\n')
    rows, manifest = gate.read_input(path, len(prefix))
    assert rows == [{'new': True}]
    assert manifest['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest['prefix_sha256'] == hashlib.sha256(prefix).hexdigest()
    with pytest.raises(ValueError, match='line boundary'):
        gate.read_input(path, len(prefix) + 1)


def live_fixture(tmp_path):
    paths = [tmp_path / name for name in ('pick.jsonl', 'carry.jsonl')]
    for path in paths:
        path.write_bytes(b'\0old snapshot bytes are never sanitized\n')
    live = gate.LiveObservationGate(*paths)
    data = fixture()
    for path, rows in zip(paths, data[1:]):
        with path.open('a') as stream:
            stream.writelines(json.dumps(row) + '\n' for row in rows)
    return live, data[0][0], paths


def test_live_gate_excludes_legacy_bytes_and_identifies_replayable_prefixes(tmp_path):
    live, row, paths = live_fixture(tmp_path)
    report = live(row)
    assert report['pick_prefix']['ee_lookup_count'] == 10
    for key, path in zip(('pick_log', 'carry_log'), paths):
        manifest = report['inputs'][key]
        assert manifest['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert manifest['byte_offset'] == len(b'\0old snapshot bytes are never sanitized\n')
    with pytest.raises(ValueError, match='reused evidence_id'):
        live(row)


@pytest.mark.parametrize('defect', ['modified_prefix', 'truncated', 'missing_final', 'partial_tail'])
def test_live_gate_cannot_continue_after_log_loss_or_replacement(tmp_path, defect):
    live, row, paths = live_fixture(tmp_path)
    path = paths[-1]
    original = path.read_bytes()
    if defect == 'modified_prefix':
        path.write_bytes(original.replace(b'old snapshot', b'NEW snapshot'))
    elif defect == 'truncated':
        path.write_bytes(b'')
    elif defect == 'missing_final':
        path.write_bytes(original.replace(b'"final": true', b'"final": false'))
    else:
        path.write_bytes(original + b'{"unfinished":')
    with pytest.raises(ValueError):
        live(row)


def test_live_gate_refuses_incomplete_logs_before_any_dispatch(tmp_path):
    pick, carry = tmp_path / 'pick.jsonl', tmp_path / 'carry.jsonl'
    pick.write_text('{}\n')
    carry.write_text('{"partial":')
    with pytest.raises(ValueError, match='partial row'):
        gate.LiveObservationGate(pick, carry)


def test_exported_live_receipt_replays_with_a_longer_final_log_snapshot(tmp_path):
    live, row, paths = live_fixture(tmp_path)
    row['carry_observation'] = live(row)
    for path, key in zip(paths, ('pick_log', 'carry_log')):
        with path.open('ab') as stream:
            stream.write(b'{"later":"unrelated row"}\n')
        data = path.read_bytes()
        offset = gate.replay_offset([row], key, data)
        assert offset == live.initial[key][0]
        changed = data.replace(b'old snapshot', b'NEW snapshot')
        with pytest.raises(ValueError, match='prefix'):
            gate.replay_offset([row], key, changed)
        changed = data.replace(b'"demo_slow"', b'"demo_fast"') if key == 'pick_log' else data.replace(b'"period_s": 0.1', b'"period_s": 0.2')
        with pytest.raises(ValueError, match='snapshot SHA'):
            gate.replay_offset([row], key, changed)
        with pytest.raises(ValueError, match='explicit offset'):
            gate.replay_offset([row], key, data, 0)


def test_cli_replays_original_live_receipts_instead_of_trusting_saved_totals(tmp_path):
    live, row, paths = live_fixture(tmp_path)
    row['carry_observation'] = live(row)
    row['carry_observation']['pick_prefix']['ee_lookup_count'] = 999  # derived display data is untrusted
    probe, receipt = tmp_path / 'A1.jsonl', tmp_path / 'probe.exit'
    probe.write_text(json.dumps(row) + '\n')
    receipt.write_text('0\n')
    out = tmp_path / 'gate.json'
    command = [sys.executable, str(SCRIPT), '--segment', 'A1', '--probe', str(probe),
               '--pick-log', str(paths[0]), '--carry-log', str(paths[1]),
               '--probe-exit', str(receipt), '--out', str(out)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_text())['trials'][0]['pick_prefix']['ee_lookup_count'] == 10


@pytest.mark.parametrize('receipt', [None, [], 'invalid', {}, {'inputs': None}, {'inputs': []}, {'inputs': {}}])
def test_malformed_live_receipt_is_rejected_as_evidence_instead_of_crashing(receipt):
    with pytest.raises(ValueError, match='receipt'):
        gate.replay_offset([{'carry_observation': receipt}], 'pick_log', b'{}\n')


def test_cli_exit_codes_no_overwrite_and_input_bytes_unchanged(tmp_path):
    data = fixture()
    paths = [tmp_path / name for name in ('A1.jsonl', 'pick.jsonl', 'carry.jsonl')]
    for path, rows in zip(paths, data):
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    receipt = tmp_path / 'probe.exit'
    receipt.write_text('0\n')
    before = {p: p.read_bytes() for p in paths + [receipt]}
    out = tmp_path / 'gate.json'
    command = [sys.executable, str(SCRIPT), '--segment', 'A1', '--probe', str(paths[0]),
               '--pick-log', str(paths[1]), '--carry-log', str(paths[2]),
               '--probe-exit', str(receipt), '--out', str(out)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    good_report = out.read_bytes()
    assert json.loads(good_report)['status'] == 'SEGMENT_EVIDENCE_COMPLETE'
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert out.read_bytes() == good_report
    assert all(path.read_bytes() == value for path, value in before.items())
    paths[2].write_text(paths[2].read_text().replace('"final": true', '"final": false'))
    command[-1] = str(tmp_path / 'incomplete.json')
    assert subprocess.run(command, capture_output=True).returncode == 1
    receipt.write_text('139\n')
    command[-1] = str(tmp_path / 'invalid.json')
    assert subprocess.run(command, capture_output=True).returncode == 2
