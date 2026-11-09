"""A complete, predeclared smoke batch is the unit of baseline admission."""
import hashlib
import json
from pathlib import Path

from flexcell_skills.contracts.episode import EPISODE_SCHEMA_VERSION, EPISODE_SCHEMA_VERSION_KEY
from flexcell_skills.contracts.routing_audit import audit_routing_episode


WINDOW_SIZE = 5


def deployment_identity(deployment):
    if deployment is None:
        return None
    fast = deployment.get('active_backends', {}).get('fast', {})
    return dict(runtime_fingerprint=deployment.get('runtime_fingerprint'),
                threshold=deployment.get('threshold'),
                fast={key: fast.get(key) for key in
                      ('model', 'model_sha256', 'calibration_sha256')})


def make_batch_plan(batch_id, counts, policy, stage, seed, protocol, digest, deployment=None):
    """Freeze scenario order and seeds before the first reset or task dispatch."""
    if type(seed) is not int or not counts:
        raise ValueError('batch requires an integer seed and scenario counts')
    if policy not in ('fsm', 'jev', 'llm', 'hybrid') or stage not in ('smoke', 'baseline'):
        raise ValueError('unsupported policy or stage')
    seen = set()
    for sid, count in counts:
        if sid in seen or sid not in protocol['scenarios']:
            raise ValueError('duplicate or unknown scenario: %s' % sid)
        if type(count) is not int or count < 1:
            raise ValueError('scenario counts must be positive integers')
        seen.add(sid)
    schedule = []
    for index in range(max(n for _, n in counts)):
        for sid, count in counts:
            if index < count:
                schedule.append(dict(scenario=sid, run=index + 1,
                                     seed=seed + len(schedule),
                                     expected=protocol['scenarios'][sid]['expect']))
    return dict(record_type='scenario_batch_plan', schema_version=1, batch_id=batch_id,
                stage=stage, policy=policy, protocol_id=protocol['protocol_id'],
                protocol_sha256=digest, seed=seed, counts=dict(counts),
                scenario_order=[sid for sid, _ in counts], schedule=schedule,
                deployment_identity=deployment_identity(deployment))


def encode_plan(plan):
    return (json.dumps(plan, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def qualify_smoke_window(summary_path, required_scenarios, policy, protocol, digest,
                         deployment=None):
    """Reject pooled, clipped, duplicated or failed windows without filtering rows.

    Native episode bytes are required and rechecked. A relocated batch can keep
    its original basename, batch_plans/ sidecar and episode basenames together.
    Legacy rows remain readable evidence, but cannot manufacture a fixed window.
    """
    summary_path = Path(summary_path)
    plan_path = summary_path.parent / 'batch_plans' / (summary_path.stem + '.json')
    raw_plan = plan_path.read_bytes()
    plan = json.loads(raw_plan)
    if not isinstance(plan, dict):
        raise ValueError('smoke plan must be an object')
    if plan.get('record_type') != 'scenario_batch_plan' or (
            type(plan.get('schema_version')) is not int or plan['schema_version'] != 1):
        raise ValueError('smoke requires a supported predeclared batch plan')
    counts, order = plan.get('counts'), plan.get('scenario_order')
    if not isinstance(counts, dict) or not isinstance(order, list) or (
            not counts or any(not isinstance(sid, str) for sid in order)
            or len(order) != len(set(order)) or set(order) != set(counts)):
        raise ValueError('smoke plan has invalid scenario counts or order')
    if any(type(n) is not int or n != WINDOW_SIZE for n in counts.values()):
        raise ValueError('qualifying smoke requires exactly five planned runs per cell')
    if not set(required_scenarios).issubset(counts):
        raise ValueError('smoke window does not cover the requested baseline cells')
    expected_plan = make_batch_plan(summary_path.stem, [(sid, counts[sid]) for sid in order],
                                    policy, 'smoke', plan.get('seed'), protocol, digest, deployment)
    # Canonical bytes distinguish bools from ints and reject non-finite values.
    if encode_plan(plan) != encode_plan(expected_plan):
        raise ValueError('smoke plan identity, protocol, schedule or deployment differs')
    plan_sha = hashlib.sha256(raw_plan).hexdigest()
    with summary_path.open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if len(rows) != len(plan['schedule']):
        raise ValueError('smoke window is incomplete or contains extra rows')
    fingerprint = None
    episodes, evidence_ids = set(), set()
    for index, (row, slot) in enumerate(zip(rows, plan['schedule']), 1):
        def reject(reason):
            raise ValueError('smoke row %d: %s' % (index, reason))
        if not isinstance(row, dict):
            reject('row must be an object')
        expected = dict(slot, batch_id=plan['batch_id'], batch_plan_sha256=plan_sha,
                        stage='smoke', policy=policy, protocol_id=protocol['protocol_id'],
                        protocol_sha256=digest)
        if any(type(row.get(key)) is not type(value) or row[key] != value
               for key, value in expected.items()):
            reject('row identity, order, seed or protocol differs from the plan')
        if (row.get('harness_error') or row.get('scenario_exercised') is not True
                or row.get('outcome') != slot['expected']):
            reject('the complete window contains a failed or unexercised check')
        expected_rc = 0 if slot['expected'] == 'SUCCEEDED' else 1
        if type(row.get('rc')) is not int or row['rc'] != expected_rc:
            reject('task client exit differs from the expected terminal outcome')
        if policy == 'fsm':
            if row.get('replay_ok') is not True:
                reject('FSM replay did not pass')
        elif type(row.get('model_decisions')) is not int or row['model_decisions'] <= 0:
            reject('no measured model decisions')
        identity = row.get('runtime_fingerprint')
        if not isinstance(identity, str) or not identity or (
                fingerprint is not None and identity != fingerprint):
            reject('missing or mixed runtime fingerprints')
        fingerprint = identity
        episode_path, evidence_id = row.get('episode'), row.get('evidence_id')
        if not isinstance(episode_path, str) or not episode_path or (
                not isinstance(evidence_id, str) or not evidence_id):
            reject('native episode path or evidence ID is missing')
        path = Path(episode_path)
        relative = row.get('episode_relative')
        if relative is not None:
            if not isinstance(relative, str) or relative in ('.', '..') or (
                    Path(relative).name != relative):
                reject('invalid portable episode basename')
            path = summary_path.parent / relative
        elif not path.is_absolute():
            path = summary_path.parent / path
        resolved = path.resolve()
        if resolved in episodes or evidence_id in evidence_ids:
            reject('duplicate native episode or evidence ID')
        episodes.add(resolved)
        evidence_ids.add(evidence_id)
        raw_episode = path.read_bytes()
        if hashlib.sha256(raw_episode).hexdigest() != row.get('episode_sha256'):
            reject('native episode bytes differ from the recorded SHA')
        record = json.loads(raw_episode)
        if not isinstance(record, dict) or any(not isinstance(record.get(key), dict)
                for key in ('final_state', 'policy', 'benchmark_protocol')):
            reject('invalid native episode structure')
        if (type(record.get(EPISODE_SCHEMA_VERSION_KEY)) is not int
                or record[EPISODE_SCHEMA_VERSION_KEY] != EPISODE_SCHEMA_VERSION):
            reject('unsupported native episode schema')
        final = record['final_state']
        if (final.get('evidence_id') != evidence_id
                or record.get('runtime_fingerprint') != fingerprint
                or record['policy'].get('name') != policy
                or record['benchmark_protocol'].get('sha256') != digest):
            reject('native episode identity differs from its summary')
        if (final.get('outcome') != str(expected_rc)
                or type(final.get('error_code')) is not int
                or (final['error_code'] == 0) != (expected_rc == 0)):
            reject('native terminal result differs from its summary')
        if deployment is not None:
            actual = audit_routing_episode(record, deployment)
            if actual.get('ok') is not True or actual != row.get('routing_audit'):
                reject('native hybrid routing evidence differs or failed')
    return fingerprint, rows
