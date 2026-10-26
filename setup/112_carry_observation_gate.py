#!/usr/bin/env python3
"""Read-only evidence gate for GRASP-B-001 Phase 3 (requires #50 telemetry).

Exit 0: this segment's recorded evidence is complete. Exit 1: stop for
incomplete/inconsistent evidence. Exit 2: invalid input or output. This never
sends robot commands and does not grant benchmark or deployment qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


SEGMENTS = {'A1': ('target_box_a', 1), 'A4': ('target_box_a', 4),
            'B5': ('target_box_b', 5)}
COUNTERS = ('ee_lookup_count', 'ee_missing_count', 'ee_missing_streak',
            'ee_missing_streak_max', 'ee_lookup_ns_total', 'ee_lookup_ns_max',
            'pin_requests', 'pin_confirmed', 'pin_failed', 'pin_skipped_no_offset')
CUMULATIVE = tuple(k for k in COUNTERS if k != 'ee_missing_streak')


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def integer(value):
    return type(value) is int and value >= 0


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def vector(value):
    return isinstance(value, list) and len(value) == 3 and all(map(finite, value))


def close(a, b):
    return math.isclose(a, b, rel_tol=0., abs_tol=1e-9)


def same_vector(a, b):
    return vector(a) and vector(b) and all(close(x, y) for x, y in zip(a, b))


def token(value):
    return (isinstance(value, str) and len(value) == 32
            and all(c in '0123456789abcdef' for c in value))


def number(row, key):
    value = row.get(key)
    require(finite(value), '%s must be finite numeric evidence' % key)
    return value


def unique(rows, message):
    require(len(rows) == 1, '%s: candidates=%d (missing or AMBIGUOUS)' % (message, len(rows)))
    return rows[0]


def reset_receipt(row):
    require(isinstance(row, dict) and row.get('ok') is True
            and type(row.get('rc')) is int and row['rc'] == 0,
            'reset must have ok=true and exit 0')
    report = row.get('report')
    require(isinstance(report, dict) and report.get('ok') is True,
            'reset report missing or not successful')
    state = report.get('report')
    require(isinstance(state, dict) and state.get('task_idle') is True
            and state.get('task_state_seen') == 'IDLE'
            and state.get('carry_disengaged') is True,
            'reset lacks confirmed IDLE / carry-disengaged boundary')


def terminal(meta, success):
    require(isinstance(meta, dict) and meta.get('accepted') is True
            and meta.get('terminal_confirmed') is True
            and meta.get('harness_error', 'MISSING') is None
            and type(meta.get('ros_status')) is int
            and meta['ros_status'] == (4 if success else 6)
            and token(meta.get('goal_uuid')),
            'action acceptance / terminal result / goal identity is incomplete')


def validate_summaries(rows, object_name, session):
    require(bool(rows), 'missing teleport_loop_summary; old silent loop is ineligible')
    previous = None
    last_periodic = None
    for row in rows:
        require(row.get('object') == object_name and row.get('session') == session
                and row.get('backend') == 'teleport'
                and type(row.get('schema_version')) is int and row['schema_version'] == 1,
                'summary identity / backend / schema mismatch')
        require(type(row.get('final')) is bool, 'summary final must be a boolean')
        require(all(integer(row.get(k)) for k in COUNTERS),
                'summary counters must be nonnegative integers, never booleans')
        require(integer(row.get('started_mono_ns')) and integer(row.get('sample_mono_ns')),
                'summary monotonic timestamps missing or invalid')
        start, sample = row['started_mono_ns'], row['sample_mono_ns']
        require(sample >= start, 'summary time precedes worker start')
        period = number(row, 'period_s')
        require(period > 0, 'period_s must be positive')
        number(row, 'wall_ts')
        n, missing = row['ee_lookup_count'], row['ee_missing_count']
        require(n == missing + row['pin_requests'] + row['pin_skipped_no_offset'],
                'lookup denominator does not reconcile')
        require(row['pin_requests'] == row['pin_confirmed'] + row['pin_failed'],
                'pin denominator does not reconcile')
        require(row['ee_missing_streak'] <= row['ee_missing_streak_max'] <= missing <= n,
                'missing lookup streak/count is inconsistent')
        require(not missing or row['ee_missing_streak_max'] > 0,
                'missing lookups require a nonzero longest streak')
        require(missing != n or row['ee_missing_streak'] == row['ee_missing_streak_max'] == n,
                'all-missing lookups require a full-length missing streak')
        total, maximum = row['ee_lookup_ns_total'], row['ee_lookup_ns_max']
        require(maximum <= total <= sample - start and total <= n * maximum,
                'lookup duration is inconsistent with count / elapsed time')
        require(n != 0 or maximum == 0, 'zero lookups cannot have lookup duration')
        require(missing != 0 or row['ee_missing_streak_max'] == 0,
                'zero missing lookups cannot have a missing streak')
        if previous is not None:
            require(not previous['final'], 'summary appears after final record')
            require(start == previous['started_mono_ns'] and period == previous['period_s'],
                    'worker start / period changed within a session')
            require(sample >= previous['sample_mono_ns']
                    and row['wall_ts'] >= previous['wall_ts'], 'summary time went backwards')
            require(all(row[k] >= previous[k] for k in CUMULATIVE),
                    'cumulative counters decreased within a session')
        if not row['final']:
            require(sample - (last_periodic if last_periodic is not None else start) >= 1_000_000_000,
                    'periodic summaries exceed the declared one-per-second rate')
            last_periodic = sample
        previous = row
    require(rows[-1]['final'], 'missing final worker summary; release is not inferred')
    require(rows[-1]['ee_lookup_count'] > 0, 'no completed end-effector lookup was observed')


def counts(row):
    return dict({k: row[k] for k in COUNTERS},
                sample_wall_ts=row['wall_ts'],
                ee_missing_fraction=(row['ee_missing_count'] / row['ee_lookup_count']
                                     if row['ee_lookup_count'] else None))


def audit_trial(row, picks, carry, object_name):
    require(row.get('object_name') == object_name, 'unexpected probe object')
    require(row.get('harness_error', 'MISSING') is None, 'probe harness error or missing harness status')
    require(type(row.get('pick_ok')) is bool, 'pick_ok must be a boolean')
    success = row['pick_ok']
    require(all(integer(row.get(k)) for k in ('outcome', 'status', 'error_code')),
            'typed pick outcome / status / error code is missing')
    require((row['outcome'], row['status']) == ((0, 1) if success else (1, 2))
            and ((row['error_code'] == 0) if success else (row['error_code'] > 0)),
            'inconsistent typed physical result')
    require(row.get('grasp_attached') is success, 'grasp_attached contradicts typed result')
    terminal(row.get('action'), success)
    pre = row.get('precondition')
    require(isinstance(pre, dict) and pre.get('ok') is True, 'probe precondition missing or failed')
    reset_receipt(pre.get('reset'))
    clear = pre.get('injection_clear')
    require(isinstance(clear, dict) and type(clear.get('rc')) is int and clear['rc'] == 0,
            'injection clear was not confirmed')
    reset_receipt(row.get('cleanup'))
    if success:
        release = row.get('release')
        terminal(release, True)
        require(all(type(release.get(k)) is int for k in ('outcome', 'status', 'error_code'))
                and (release['outcome'], release['status'], release['error_code']) == (0, 1, 0)
                and release.get('released') is True
                and isinstance(release.get('evidence_id'), str) and bool(release['evidence_id'])
                and vector(release.get('measured_after')), 'PLACE release evidence is incomplete')
    else:
        require('release' not in row, 'failed PICK unexpectedly has a subsequent PLACE')
    evidence_id = row.get('evidence_id')
    require(isinstance(evidence_id, str) and bool(evidence_id), 'missing PICK evidence_id')
    pick = unique([p for p in picks if p.get('evidence_id') == evidence_id], 'PICK evidence_id match')
    require(pick.get('object_name') == object_name and pick.get('profile') == 'demo_slow'
            and not pick.get('injected') and not str(pick.get('detail', '')).startswith('injected failure'),
            'PICK object / profile mismatch or injected observation')
    require(str(pick.get('outcome')) == str(row['outcome'])
            and all(type(pick.get(k)) is int and pick[k] == row[k] for k in ('status', 'error_code')),
            'PICK stage log contradicts probe result')
    require(same_vector(row.get('before'), pick.get('box_before'))
            and same_vector(row.get('after'), pick.get('box_after')),
            'PICK measured poses missing or disagree with probe')
    rise = number(row, 'rise_m')
    require(close(rise, number(pick, 'box_rise_m'))
            and close(rise, row['after'][2] - row['before'][2]), 'measured rise does not reconcile')
    require(not success or rise > 0, 'success contradicts nonpositive measured rise')
    require(number(pick, 'attach_gap_m') >= 0 and vector(pick.get('carry_offset')),
            'attach gap / carry offset evidence is missing')
    end = number(pick, 'wall_ts')
    require(integer(pick.get('elapsed_ms')), 'PICK elapsed_ms must be a nonnegative integer')
    # elapsed_ms is truncated to integer milliseconds by PickServer.finish.
    begin = end - pick['elapsed_ms'] / 1000. - .001
    candidates = [c for c in carry if c.get('event') == 'start'
                  and c.get('object') == object_name and finite(c.get('wall_ts'))
                  and begin <= c['wall_ts'] <= end]
    start = unique(candidates, 'object/time carry start match')
    session = start.get('session')
    require(token(session) and start.get('backend') == 'teleport', 'carry session / backend mismatch')
    events = [c for c in carry if c.get('session') == session]
    unique([c for c in events if c.get('event') == 'start'], 'session start identity')
    require(same_vector(start.get('offset'), pick['carry_offset']), 'carry offset disagrees with PICK')
    summaries = [c for c in events if c.get('event') == 'teleport_loop_summary']
    validate_summaries(summaries, object_name, session)
    stop = unique([c for c in events if c.get('event') == 'stop'], 'session stop identity')
    require(stop.get('object') == object_name and stop.get('backend') == 'teleport'
            and stop.get('engaged') is True and stop.get('cause') in
            ('release', 'replace', 'worker_ended', 'shutdown', 'topic', 'unspecified'),
            'session stop identity / cause is incomplete')
    require(number(stop, 'wall_ts') >= summaries[-1]['wall_ts'] >= start['wall_ts'],
            'final/stop timestamps precede the matched session start')
    prefix = [s for s in summaries if start['wall_ts'] <= s['wall_ts'] <= end]
    require(bool(prefix), 'no summary observed during the PICK interval')
    return dict(trial=row['trial'], object_name=object_name, evidence_id=evidence_id,
                goal_uuid=row['action']['goal_uuid'], session=session,
                association='OBJECT_TIME_UNIQUE_NOT_GOAL_UUID', pick_ok=success,
                error_code=row['error_code'], rise_m=rise,
                pick_prefix=counts(prefix[-1]), pick_prefix_age_s=end - prefix[-1]['wall_ts'],
                session_totals=counts(summaries[-1]), stop_cause=stop['cause'])


def audit_segment(segment, probes, picks, carry, probe_rc):
    object_name, expected = SEGMENTS[segment]
    errors, trials = [], []
    if type(probe_rc) is not int or probe_rc != 0:
        errors.append('probe process did not exit 0')
    if len(probes) != expected or [r.get('trial') for r in probes] != list(range(1, expected + 1)):
        errors.append('segment must contain exactly its prescribed trials, in order, without refill')
    for row in probes:
        try:
            require(type(row.get('trial')) is int, 'trial identity must be an integer')
            trials.append(audit_trial(row, picks, carry, object_name))
        except EvidenceError as exc:
            errors.append('trial %r: %s' % (row.get('trial'), exc))
    for key in ('evidence_id', 'goal_uuid', 'session'):
        if len({r[key] for r in trials}) != len(trials):
            errors.append('reused %s across trials' % key)
    return dict(schema_version=1, segment=segment,
                status='STOP_INCOMPLETE_EVIDENCE' if errors else 'SEGMENT_EVIDENCE_COMPLETE',
                expected_trials=expected, observed_trials=len(probes), checked_trials=len(trials),
                probe_reported_successes=sum(r.get('pick_ok') is True for r in probes),
                probe_reported_failures=sum(r.get('pick_ok') is False for r in probes),
                trials=trials, errors=errors, root_cause='UNKNOWN',
                scope='segment evidence only; no robot commands, runtime health or qualification granted')


def strict_pairs(pairs):
    row = {}
    for key, value in pairs:
        require(key not in row, 'duplicate JSON key %r' % key)
        row[key] = value
    return row


def json_number(value):
    parsed = float(value)
    require(math.isfinite(parsed), 'nonfinite JSON number')
    return parsed


def invalid_constant(value):
    raise EvidenceError('invalid JSON numeric constant %s' % value)


def read_input(path, offset=0, jsonl=True, data=None):
    if data is None:
        data = path.read_bytes()
    require(0 <= offset <= len(data) and (offset == 0 or data[offset - 1:offset] == b'\n'),
            '%s: offset must be an existing JSONL line boundary' % path)
    manifest = dict(path=str(path), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    byte_offset=offset, prefix_sha256=hashlib.sha256(data[:offset]).hexdigest())
    text = data[offset:].decode('utf-8')
    if not jsonl:
        return text, manifest
    rows = []
    for line_number, line in enumerate(text.splitlines(), 1 + data[:offset].count(b'\n')):
        if not line.strip():
            continue
        try:
            row = json.loads(line, object_pairs_hook=strict_pairs, parse_float=json_number,
                             parse_constant=invalid_constant)
            require(isinstance(row, dict), 'JSONL row must be an object')
        except ValueError as exc:
            raise EvidenceError('%s:%d: %s' % (path, line_number, exc)) from exc
        rows.append(row)
    return rows, manifest


class LiveObservationGate:
    """Check after confirmed cleanup, before the existing probe's next trial.

    Pre-existing log bytes are retained, hashed and excluded explicitly. Each
    receipt describes the bytes read at that instant; a final full log snapshot
    must retain those prefixes so they can be checked again after export.
    """

    def __init__(self, pick_log, carry_log):
        self.paths = {'pick_log': Path(pick_log), 'carry_log': Path(carry_log)}
        self.initial = {}
        self.seen = {key: set() for key in ('evidence_id', 'goal_uuid', 'session')}
        for key, path in self.paths.items():
            data = path.read_bytes()
            require(not data or data.endswith(b'\n'), '%s: initial log ends in a partial row' % path)
            self.initial[key] = (len(data), hashlib.sha256(data).hexdigest())

    def __call__(self, row):
        logs, manifests = {}, {}
        for key, path in self.paths.items():
            offset, digest = self.initial[key]
            logs[key], manifests[key] = read_input(path, offset)
            require(manifests[key]['prefix_sha256'] == digest,
                    '%s: pre-existing log bytes changed during the segment' % key)
        result = audit_trial(row, logs['pick_log'], logs['carry_log'], row['object_name'])
        for key, seen in self.seen.items():
            require(result[key] not in seen, 'reused %s across trials' % key)
        for key, seen in self.seen.items():
            seen.add(result[key])
        return dict(result, inputs=manifests)


def replay_offset(probes, key, data, explicit=None):
    """Recheck the live gate's captured bytes against the exported full log."""
    receipts = []
    for row in probes:
        if 'carry_observation' not in row:
            receipts.append(None)
            continue
        observation = row['carry_observation']
        require(isinstance(observation, dict) and isinstance(observation.get('inputs'), dict),
                'malformed live gate observation / inputs receipt')
        require(isinstance(observation['inputs'].get(key), dict), 'missing live gate log receipt')
        receipts.append(observation['inputs'][key])
    if not any(r is not None for r in receipts):
        return explicit if explicit is not None else 0
    require(all(isinstance(r, dict) for r in receipts), 'mixed or missing live gate receipts')
    offset = receipts[0].get('byte_offset')
    require(integer(offset) and offset <= len(data), 'invalid live gate byte offset')
    if explicit is not None:
        require(explicit == offset, 'explicit offset disagrees with the live gate receipt')
    prefix_sha = hashlib.sha256(data[:offset]).hexdigest()
    for receipt in receipts:
        size = receipt.get('size_bytes')
        require(receipt.get('byte_offset') == offset and receipt.get('prefix_sha256') == prefix_sha
                and integer(size) and offset <= size <= len(data),
                'exported log lost / changed a captured live gate prefix')
        require(hashlib.sha256(data[:size]).hexdigest() == receipt.get('sha256'),
                'exported log bytes disagree with the live gate snapshot SHA')
    return offset


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--segment', required=True, choices=SEGMENTS)
    for name in ('probe', 'pick-log', 'carry-log', 'probe-exit', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--pick-offset', type=int, help='default: captured live offset, otherwise 0')
    parser.add_argument('--carry-offset', type=int, help='default: captured live offset, otherwise 0')
    args = parser.parse_args(argv)
    manifests = {}
    try:
        probes, manifests['probe'] = read_input(args.probe)
        pick_bytes, carry_bytes = args.pick_log.read_bytes(), args.carry_log.read_bytes()
        pick_offset = replay_offset(probes, 'pick_log', pick_bytes, args.pick_offset)
        carry_offset = replay_offset(probes, 'carry_log', carry_bytes, args.carry_offset)
        picks, manifests['pick_log'] = read_input(args.pick_log, pick_offset, data=pick_bytes)
        carry, manifests['carry_log'] = read_input(args.carry_log, carry_offset, data=carry_bytes)
        receipt, manifests['probe_exit'] = read_input(args.probe_exit, jsonl=False)
        require(receipt.strip() == '0', 'probe exit receipt must contain 0')
        report = audit_segment(args.segment, probes, picks, carry, 0)
        rc = 1 if report['errors'] else 0
    except (OSError, ValueError, OverflowError) as exc:
        report = dict(schema_version=1, segment=args.segment, status='STOP_INVALID_INPUT',
                      errors=[str(exc)], root_cause='UNKNOWN')
        rc = 2
    report['inputs'] = manifests
    try:
        with args.out.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except OSError as exc:
        print('STOP: cannot create a new report: %s' % exc, file=sys.stderr)
        return 2
    print('%s: %s' % (report['status'], args.out))
    for error in report.get('errors', []):
        print('  ' + error, file=sys.stderr)
    return rc


if __name__ == '__main__':
    sys.exit(main())
