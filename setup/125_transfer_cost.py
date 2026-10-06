#!/usr/bin/env python3
"""Offline transfer-cost ledger. No ROS, network calls, or acceptance runner.

The v1 instrument records costs and diagnostic trials; AC@90 is frozen.
Evidence files must be immutable snapshots, not live appendable logs.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid


class LedgerError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise LedgerError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise LedgerError('non-finite JSON value: ' + value)


def decode(raw):
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected.split()),
            'unexpected or missing fields: expected ' + expected)


def text_value(value, name):
    require(type(value) is str and bool(value.strip()), name + ' must be text')


def number(value, name, integer=False, nullable=False):
    if value is None and nullable:
        return
    allowed = (int,) if integer else (int, float)
    require(type(value) in allowed and 0 <= value <= 2**63 - 1
            and (type(value) is int or math.isfinite(value)),
            name + ' must be a finite nonnegative number (not bool)')


def sha_value(value, name, nullable=False, lengths=(64,)):
    if value is None and nullable:
        return
    require(type(value) is str and len(value) in lengths
            and all(c in '0123456789abcdef' for c in value), name + ' invalid digest')


def pin(path):
    path = Path(path).expanduser().resolve(strict=True)
    require(path.is_file(), 'evidence must be a regular file: ' + str(path))
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_pins(values):
    require(type(values) is list and bool(values), 'nonempty evidence list required')
    seen = set()
    for item in values:
        keys(item, 'path sha256')
        text_value(item['path'], 'evidence path')
        require(Path(item['path']).is_absolute(), 'evidence path must be absolute')
        sha_value(item['sha256'], 'evidence sha256')
        require(item['path'] not in seen, 'duplicate evidence path')
        require(pin(item['path']) == item, 'evidence changed: ' + item['path'])
        seen.add(item['path'])


def validate_plan(plan):
    keys(plan, 'schema_version protocol_id record_kind migration_axis arms cases '
         'baseline_revisions qualification freeze_artifacts')
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1,
            'schema_version must be 1')
    text_value(plan['protocol_id'], 'protocol_id')
    require(plan['record_kind'] in ('DRAFT_PLAN', 'PROSPECTIVE_PLAN',
                                  'SYNTHETIC_TOOL_FIXTURE'), 'unknown record_kind')
    require(plan['migration_axis'] in ('T1', 'T2', 'T3', 'T4', 'T5'), 'unknown axis')
    for name in ('arms', 'cases'):
        values = plan[name]
        require(type(values) is list and bool(values), name + ' must be nonempty')
        for value in values:
            text_value(value, name)
        require(len(values) == len(set(values)), name + ' must be unique')
    require(type(plan['baseline_revisions']) is dict
            and set(plan['baseline_revisions']) == set(plan['arms']),
            'one baseline revision per arm required')
    for value in plan['baseline_revisions'].values():
        sha_value(value, 'baseline_revision', lengths=(40,))
    require(plan['qualification'] == {
        'status': 'FROZEN', 'target_success_rate': 0.9},
        'v1 qualification must remain FROZEN at target 0.9')
    artifacts = plan['freeze_artifacts']
    require(type(artifacts) is dict, 'freeze_artifacts must be an object')
    for name, value in artifacts.items():
        text_value(name, 'artifact name')
        validate_pins([value])
    if plan['record_kind'] == 'PROSPECTIVE_PLAN':
        required = {'task_manifest', 'initial_states', 'success_predicate',
                    'skill_contracts'} | {'baseline_config/' + arm for arm in plan['arms']}
        require(required <= set(artifacts), 'prospective plan missing frozen manifests')


def validate_event(event, plan, prior):
    require(type(event) is dict, 'event must be an object')
    kind = event.get('kind')
    common = 'event_id kind arm '
    fields = {
        'effort_start': 'session_id actor activity clock_id start_ns',
        'effort_stop': 'session_id clock_id end_ns evidence',
        'effort_unknown': 'session_id reason evidence',
        'trial': 'trial_id purpose case_id runtime_fingerprint calibration_sha256 '
                 'reported_outcome return_code evidence',
        'api': 'request_id scope input_tokens output_tokens amount currency evidence',
        'change_snapshot': 'base_revision target_revision code_added code_deleted '
                           'config_added config_deleted rules_added states_added evidence',
    }
    require(kind in fields, 'unknown event kind')
    keys(event, common + fields[kind])
    text_value(event['event_id'], 'event_id')
    require(event['event_id'] not in {e['event_id'] for e in prior}, 'duplicate event_id')
    require(event['arm'] in plan['arms'], 'arm absent from frozen plan')
    if 'evidence' in event:
        validate_pins(event['evidence'])
    if kind in ('trial', 'api'):
        require(len(event['evidence']) == 1,
                'one independent primary receipt required; shared support belongs in freeze_artifacts')
    if kind.startswith('effort_'):
        text_value(event['session_id'], 'session_id')
        starts = [e for e in prior if e['kind'] == 'effort_start'
                  and e['session_id'] == event['session_id']]
        if kind == 'effort_start':
            text_value(event['clock_id'], 'clock_id')
            require(not starts, 'session_id already used')
            require(event['actor'] in ('human', 'coding_agent', 'wait'), 'unknown actor')
            text_value(event['activity'], 'activity')
            number(event['start_ns'], 'start_ns', integer=True)
            # A person cannot book two concurrent active sessions. Other actors
            # are separate clocks/cost dimensions, not added to person-minutes.
            closed = {e['session_id'] for e in prior if e['kind'] in ('effort_stop', 'effort_unknown')}
            exclusive = {'human', 'wait'} if event['actor'] in ('human', 'wait') else {'coding_agent'}
            require(not any(e['kind'] == 'effort_start' and e['actor'] in exclusive
                            and e['session_id'] not in closed for e in prior),
                    'actor already has an open session; stop human before pure wait')
        else:
            require(len(starts) == 1, 'unknown effort session')
            start = starts[0]
            require(not any(e['kind'] in ('effort_stop', 'effort_unknown')
                            and e['session_id'] == event['session_id'] for e in prior),
                    'effort session already stopped')
            require(start['arm'] == event['arm'], 'effort arm mismatch')
            if kind == 'effort_stop':
                require(start['clock_id'] == event['clock_id'], 'effort boot-clock mismatch')
                number(event['end_ns'], 'end_ns', integer=True)
                require(event['end_ns'] >= start['start_ns'], 'negative effort interval')
            else:
                text_value(event['reason'], 'unknown effort reason')
    elif kind == 'trial':
        text_value(event['trial_id'], 'trial_id')
        require(event['trial_id'] not in {e['trial_id'] for e in prior if e['kind'] == 'trial'},
                'duplicate trial_id; retain failure instead of replacing it')
        require(event['purpose'] in ('adaptation', 'regression'),
                'qualification sampling is frozen in v1')
        require(event['case_id'] in plan['cases'], 'case absent from frozen plan')
        sha_value(event['runtime_fingerprint'], 'runtime_fingerprint')
        sha_value(event['calibration_sha256'], 'calibration_sha256', nullable=True)
        require(event['reported_outcome'] in ('SUCCEEDED', 'FAILED', 'HARNESS_ERROR', 'UNKNOWN'),
                'unknown reported_outcome')
        require(event['return_code'] is None or type(event['return_code']) is int,
                'return_code must be integer or null')
        trial_digests = {p['sha256'] for e in prior if e['kind'] == 'trial' for p in e['evidence']}
        require(not any(p['sha256'] in trial_digests for p in event['evidence']),
                'trial evidence already used; copy does not create a new trial')
    elif kind == 'api':
        text_value(event['request_id'], 'request_id')
        require(event['request_id'] not in {e['request_id'] for e in prior if e['kind'] == 'api'},
                'duplicate request_id')
        api_digests = {p['sha256'] for e in prior if e['kind'] == 'api' for p in e['evidence']}
        require(event['evidence'][0]['sha256'] not in api_digests,
                'API receipt already used; different ID does not create a new request')
        require(event['scope'] in ('adaptation', 'evaluation', 'calibration', 'coding'),
                'unknown API scope')
        for name in ('input_tokens', 'output_tokens'):
            number(event[name], name, integer=True, nullable=True)
        number(event['amount'], 'amount', nullable=True)
        text_value(event['currency'], 'currency')
    else:
        sha_value(event['base_revision'], 'base_revision', lengths=(40,))
        sha_value(event['target_revision'], 'target_revision', lengths=(40,))
        require(event['base_revision'] == plan['baseline_revisions'][event['arm']],
                'change snapshot baseline differs from plan')
        for name in ('code_added', 'code_deleted', 'config_added', 'config_deleted',
                     'rules_added', 'states_added'):
            number(event[name], name, integer=True, nullable=True)


def read_rows(raw):
    require(bool(raw) and raw.endswith(b'\n'), 'empty or incomplete ledger; preserve for audit')
    rows, prior, plan = [], [], None
    for seq, line in enumerate(raw.splitlines()):
        row = decode(line)
        keys(row, 'seq previous_sha256 payload sha256')
        require(type(row['seq']) is int and row['seq'] == seq, 'ledger sequence mismatch')
        require(row['previous_sha256'] == (rows[-1]['sha256'] if rows else None),
                'ledger chain mismatch')
        require(row['sha256'] == digest({k: row[k] for k in row if k != 'sha256'}),
                'ledger row digest mismatch')
        payload = row['payload']
        if seq == 0:
            keys(payload, 'kind created_utc plan')
            require(payload['kind'] == 'plan', 'first row must freeze a plan')
            text_value(payload['created_utc'], 'created_utc')
            plan = payload['plan']
            validate_plan(plan)
        else:
            require(type(payload) is dict, 'event must be object')
            validate_event(payload, plan, prior)
            prior.append(payload)
        rows.append(row)
    return rows


def row_bytes(payload, rows):
    row = {'seq': len(rows), 'previous_sha256': rows[-1]['sha256'] if rows else None,
           'payload': payload}
    row['sha256'] = digest(row)
    return canonical(row) + b'\n'


def initialize(path, plan):
    validate_plan(plan)
    payload = {'kind': 'plan', 'created_utc': datetime.now(timezone.utc).isoformat(), 'plan': plan}
    # Exclusive creation: never reset an existing experiment's ledger.
    with Path(path).open('xb') as stream:
        stream.write(row_bytes(payload, []))
        stream.flush()
        os.fsync(stream.fileno())


def append(path, event, stamp_start=False):
    with Path(path).open('r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        rows = read_rows(stream.read())
        prior = [r['payload'] for r in rows[1:]]
        validate_event(event, rows[0]['payload']['plan'], prior)
        if stamp_start:
            require(event['kind'] == 'effort_start', 'only effort_start can sample its clock')
            # Exclude lock acquisition, historical hashing, and event validation
            # from the operator's measured session.
            event = dict(event, start_ns=time.perf_counter_ns())
        stream.seek(0, 2)
        stream.write(row_bytes(event, rows))
        stream.flush()
        os.fsync(stream.fileno())


def read_ledger(path):
    with Path(path).open('rb') as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        return read_rows(stream.read())


def summarize(rows):
    plan = rows[0]['payload']['plan']
    events = [r['payload'] for r in rows[1:]]
    effort = defaultdict(Counter)
    starts = {e['session_id']: e for e in events if e['kind'] == 'effort_start'}
    stopped = set()
    unmeasured = []
    api = {}
    trials = defaultdict(Counter)
    changes = {}
    for e in events:
        if e['kind'] == 'effort_stop':
            start = starts[e['session_id']]
            effort[e['arm']][start['actor']] += (e['end_ns'] - start['start_ns']) / 60e9
            stopped.add(e['session_id'])
        elif e['kind'] == 'effort_unknown':
            stopped.add(e['session_id'])
            unmeasured.append(dict(e, actor=starts[e['session_id']]['actor']))
        elif e['kind'] == 'api':
            key = (e['arm'], e['scope'], e['currency'])
            cell = api.setdefault(key, {'requests': 0, 'known_amount_subtotal': 0,
                                       'unknown_amount_requests': 0, 'known_input_tokens': 0,
                                       'known_output_tokens': 0, 'unknown_token_requests': 0})
            cell['requests'] += 1
            cell['known_amount_subtotal'] += e['amount'] or 0
            cell['unknown_amount_requests'] += e['amount'] is None
            cell['known_input_tokens'] += e['input_tokens'] or 0
            cell['known_output_tokens'] += e['output_tokens'] or 0
            cell['unknown_token_requests'] += e['input_tokens'] is None or e['output_tokens'] is None
        elif e['kind'] == 'trial':
            key = (e['arm'], e['purpose'], e['case_id'], e['runtime_fingerprint'],
                   e['calibration_sha256'])
            # SIGABRT can never count as success, even when earlier JSON says ok.
            outcome = 'ABORTED_PROCESS' if e['return_code'] in (-6, 134) else e['reported_outcome']
            trials[key][outcome] += 1
        elif e['kind'] == 'change_snapshot':
            changes[e['arm']] = e  # baseline-to-head snapshots are not additive
    trial_cells = []
    attempt_totals = Counter()
    for key, counts in trials.items():
        attempt_totals[key[:2]] += sum(counts.values())
        measured = counts['SUCCEEDED'] + counts['FAILED'] + counts['ABORTED_PROCESS']
        n, successes = measured, counts['SUCCEEDED']
        z = 1.96
        lower = ((successes / n + z*z/(2*n) - z*math.sqrt(
            (successes/n)*(1-successes/n)/n + z*z/(4*n*n))) / (1+z*z/n)) if n else None
        trial_cells.append(dict(zip(('arm', 'purpose', 'case_id', 'runtime_fingerprint',
                                     'calibration_sha256'), key),
                                outcomes=dict(counts), completed_denominator=measured,
                                retained_attempts=sum(counts.values()),
                                observed_success_rate=successes/n if n else None,
                                diagnostic_wilson_95_lower=lower,
                                large_sample_review_required=sum(counts.values()) >= 50))
    return {
        'schema_version': 1, 'record_kind': plan['record_kind'], 'protocol_id': plan['protocol_id'],
        'plan_sha256': digest(plan), 'ledger_tail_sha256': rows[-1]['sha256'],
        'accounting_basis': 'CLI timing; other values asserted from pinned evidence, not auto-extracted',
        'effort_minutes': {arm: {actor: effort[arm].get(actor) for actor in ('human', 'coding_agent', 'wait')}
                           for arm in plan['arms']},
        'effort_status': {arm: {actor: (
            'INCOMPLETE' if any(e['arm'] == arm and e['actor'] == actor for e in unmeasured)
            or any(sid not in stopped and e['arm'] == arm and e['actor'] == actor
                   for sid, e in starts.items()) else
            'RECORDED' if actor in effort[arm] else 'NOT_RUN')
            for actor in ('human', 'coding_agent', 'wait')} for arm in plan['arms']},
        'open_effort_sessions': [e for sid, e in starts.items() if sid not in stopped],
        'unmeasured_effort_sessions': unmeasured,
        'api_usage': [dict(zip(('arm', 'scope', 'currency'), key), **value,
                           amount_status='INCOMPLETE' if value['unknown_amount_requests'] else 'RECORDED')
                      for key, value in api.items()],
        'latest_change_snapshot': changes, 'trial_cells': trial_cells,
        'attempt_totals': [dict(arm=key[0], purpose=key[1], retained_attempts=n,
                                large_sample_review_required=n >= 50)
                           for key, n in attempt_totals.items()],
        'AC@90': {'status': 'NOT_RUN', 'reason': 'v1 qualification is FROZEN'},
        'decision_latency': {'status': 'NOT_RUN', 'reason': 'use episode perf_counter_ns measurements'},
        'safety_acceptance': {'status': 'NOT_RUN', 'reason': 'no physical safety evaluation in this tool'},
    }


def clock_id():
    return 'perf_counter_ns/linux-boot/' + Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='freeze plan in a new ledger, refuse overwrite')
    init.add_argument('--spec', type=Path, required=True)
    start = sub.add_parser('start', help='begin one active timed session')
    start.add_argument('--arm', required=True)
    start.add_argument('--session', required=True)
    start.add_argument('--actor', choices=('human', 'coding_agent', 'wait'), required=True)
    start.add_argument('--activity', required=True)
    stop = sub.add_parser('stop', help='finish session using same Linux boot clock')
    stop.add_argument('--session', required=True)
    stop.add_argument('--evidence', type=Path, action='append', required=True)
    unknown = sub.add_parser('close-unknown', help='retain an unmeasured session and permit continuation')
    unknown.add_argument('--session', required=True)
    unknown.add_argument('--reason', required=True)
    unknown.add_argument('--evidence', type=Path, action='append', required=True)
    record = sub.add_parser('record', help='append a typed trial, API, or change receipt')
    record.add_argument('--event', type=Path, required=True)
    report = sub.add_parser('report', help='verify all hashes and emit JSON; AC@90 remains NOT_RUN')
    report.add_argument('--out', type=Path)
    for command in (init, start, stop, unknown, record, report):
        command.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            plan = decode(args.spec.read_bytes())
            require(type(plan) is dict and type(plan.get('freeze_artifacts')) is dict,
                    'spec requires an object with freeze_artifacts mapping')
            plan['freeze_artifacts'] = {name: pin(path) for name, path in plan['freeze_artifacts'].items()}
            initialize(args.ledger, plan)
        elif args.command == 'start':
            append(args.ledger, dict(kind='effort_start', event_id=str(uuid.uuid4()),
                                    arm=args.arm, session_id=args.session, actor=args.actor,
                                    activity=args.activity, clock_id=clock_id(), start_ns=0), stamp_start=True)
        elif args.command in ('stop', 'close-unknown'):
            now = time.perf_counter_ns()
            rows = read_ledger(args.ledger)
            starts = [r['payload'] for r in rows[1:] if r['payload']['kind'] == 'effort_start'
                      and r['payload']['session_id'] == args.session]
            require(len(starts) == 1, 'unknown effort session')
            event = dict(event_id=str(uuid.uuid4()), arm=starts[0]['arm'], session_id=args.session,
                         evidence=[pin(p) for p in args.evidence])
            if args.command == 'stop':
                event.update(kind='effort_stop', clock_id=clock_id(), end_ns=now)
            else:
                event.update(kind='effort_unknown', reason=args.reason)
            append(args.ledger, event)
        elif args.command == 'record':
            event = decode(args.event.read_bytes())
            require(type(event) is dict, 'event must be an object')
            require(event.get('kind') in ('trial', 'api', 'change_snapshot'),
                    'use start/stop commands for real timing')
            event['evidence'] = [pin(p) for p in event['evidence']]
            append(args.ledger, event)
        else:
            result = summarize(read_ledger(args.ledger))
            output = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
            if args.out:
                with args.out.open('x', encoding='utf-8') as stream:
                    stream.write(output)
            else:
                print(output, end='')
        return 0
    except (LedgerError, OSError, ValueError, TypeError, KeyError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
