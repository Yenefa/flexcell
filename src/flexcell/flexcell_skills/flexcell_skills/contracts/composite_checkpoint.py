"""Validate a measured paused prefix and consume its resume claim exactly once.

No missing/unknown terminal, crash tail, failed task or legacy receipt authorizes
replay. A claim remains consumed after failure or interruption of the resume.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re

from flexcell_skills.contracts.composite import CompositeError, matches, native_success, positions, vacant, validate_plan
from flexcell_skills.contracts.episode import _sanitize


def require(value, detail):
    if not value:
        raise CompositeError(65, detail)


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def validate_paused(events, plan, fingerprint, read_episode):
    """Recompute the prefix from every native result and measured boundary."""
    plan = validate_plan(plan)
    require(type(events) is list and len(events) >= 7 and all(type(e) is dict for e in events), 'incomplete paused journal')
    first, terminal = events[0], events[-1]
    identity = ('record_kind', 'run_id', 'goal_uuid', 'runtime_fingerprint', 'policy', 'policy_version', 'contract_version')
    for seq, event in enumerate(events):
        require(type(event.get('seq')) is int and event['seq'] == seq
                and all(k in first and event.get(k) == first[k] for k in identity), 'journal identity/sequence mismatch')
    require(first['record_kind'] == 'ACTUAL_COMPOSITE_TASK' and type(first['contract_version']) is int
            and first['contract_version'] == 2, 'resume requires contract v2')
    require(type(fingerprint) is str and re.fullmatch('[0-9a-f]{64}', fingerprint)
            and first['runtime_fingerprint'] == fingerprint, 'runtime identity mismatch')
    require(first.get('event') == 'PLAN' and first.get('plan') == plan and first.get('plan_sha256') == plan_digest(plan), 'original plan mismatch')
    count = first.get('pause_after_stages')
    require(type(count) is int and 0 < count < len(plan['stages']), 'invalid pause prefix')
    require(len(events) == 2 + 5*count and terminal.get('event') == 'TERMINAL'
            and type(terminal.get('outcome')) is int and terminal['outcome'] == 3
            and type(terminal.get('error_code')) is int and terminal['error_code'] == 0, 'only a confirmed requested pause can resume')
    expected = copy.deepcopy(plan['initial_objects'])
    stages, runs, goals = [], [], []
    tolerance, clearance = plan['position_tolerance_m'], plan['clearance_m']
    for index, stage in enumerate(plan['stages'][:count]):
        pre, start, native, post, committed = events[1+index*5:6+index*5]
        segment = [pre, start, native, post, committed]
        sid = stage['stage_id']
        require([e.get('event') for e in segment] == ['OBSERVATION', 'STARTED', 'NATIVE_TERMINAL', 'OBSERVATION', 'COMMITTED']
                and all(e.get('stage_id') == sid for e in segment), 'unconfirmed or reordered stage')
        require(pre.get('boundary') == 'before' and post.get('boundary') == 'after', 'measurement boundaries missing')
        actual = positions(pre.get('observation'), expected)
        require(matches(actual, expected, tolerance) and vacant(actual, stage['destination'], clearance, stage['object_name']), 'original precondition failed')
        component = native.get('component'); goal_id = start.get('component_goal_uuid')
        require(type(goal_id) is str and re.fullmatch('[0-9a-f]{32}', goal_id)
                and native_success(component, goal_id, tolerance), 'native terminal/verification missing')
        episode = read_episode(component)
        require(episode.get('run_id') == component['run_id'] and episode.get('runtime_fingerprint') == fingerprint,
                'persisted native identity mismatch')
        require(episode.get('policy') == {'name':first['policy'], 'version':first['policy_version']}, 'persisted native policy mismatch')
        final = episode.get('final_state') or {}
        require(final == _sanitize(component['final_state']) and final.get('parent_run_id') == first['run_id']
                and final.get('stage_id') == sid and final.get('execution_kind') == 'IN_PROCESS_COMPONENT'
                and final.get('component_execution_id') == goal_id, 'persisted native final state mismatch')
        steps = episode.get('steps') or []
        require(bool(steps) and all(s['policy_input']['goal']['assignments'] == [[stage['object_name'], 'task_place']] for s in steps), 'native target mismatch')
        for action in ('PICK', 'PLACE', 'VERIFY'):
            require(any(s['policy_output']['action'] == action and s['policy_output']['target'] == stage['object_name']
                        and type((s.get('executor_result') or {}).get('outcome')) is int
                        and s['executor_result']['outcome'] == 0 for s in steps), 'native action unconfirmed: ' + action)
        expected[stage['object_name']] = list(stage['destination'])
        require(matches(positions(post.get('observation'), expected), expected, tolerance)
                and committed.get('expected_positions') == expected and committed.get('component_run_id') == component['run_id'], 'committed state unconfirmed')
        stages.append(sid); runs.append(component['run_id']); goals.append(goal_id)
    require(len(set(runs)) == count and len(set(goals)) == count
            and terminal.get('completed_stage_ids') == stages and terminal.get('component_run_ids') == runs
            and terminal.get('component_goal_uuids') == goals, 'paused progress mismatch')
    return dict(source_run_id=first['run_id'], policy=first['policy'], policy_version=first['policy_version'],
                plan_sha256=plan_digest(plan), expected_positions=expected,
                completed_stage_ids=stages, component_run_ids=runs, component_goal_uuids=goals)


def load_checkpoint(directory, run_id, digest, plan, fingerprint, episode_directory):
    require(type(run_id) is str and re.fullmatch('composite-[0-9a-f]{16}', run_id), 'invalid source run ID')
    require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'receipt SHA256 required')
    root = Path(directory).expanduser().resolve()
    path = root / (run_id + '.jsonl')
    require(path.is_file() and not path.is_symlink(), 'server-owned receipt missing')
    raw = path.read_bytes(); require(hashlib.sha256(raw).hexdigest() == digest, 'receipt hash mismatch')
    def invalid_number(value):
        raise CompositeError(65, 'nonfinite receipt number: ' + value)
    events = [json.loads(line, parse_constant=invalid_number) for line in raw.decode().splitlines()]
    episode_root = Path(episode_directory).expanduser().resolve()
    def read_episode(component):
        p = Path(component['episode_path']).expanduser()
        require(p.is_file() and not p.is_symlink() and p.resolve().parent == episode_root, 'native episode is outside server storage')
        return json.loads(p.read_text(), parse_constant=invalid_number)
    checkpoint = validate_paused(events, plan, fingerprint, read_episode)
    require(checkpoint['source_run_id'] == run_id, 'source run ID mismatch')
    checkpoint['source_receipt_sha256'] = digest
    return checkpoint


def claim_checkpoint(directory, checkpoint, resumed_run_id):
    require(type(checkpoint.get('source_run_id')) is str and re.fullmatch('composite-[0-9a-f]{16}', checkpoint['source_run_id']), 'invalid claim source ID')
    require(type(checkpoint.get('source_receipt_sha256')) is str and re.fullmatch('[0-9a-f]{64}', checkpoint['source_receipt_sha256']), 'invalid claim source SHA')
    require(type(resumed_run_id) is str and re.fullmatch('composite-[0-9a-f]{16}', resumed_run_id), 'invalid resumed run ID')
    root = Path(directory).expanduser()
    claim = root / (checkpoint['source_run_id'] + '.resume-claim.json')
    data = dict(record_kind='COMPOSITE_RESUME_CLAIM', source_run_id=checkpoint['source_run_id'],
                source_receipt_sha256=checkpoint['source_receipt_sha256'], resumed_run_id=resumed_run_id)
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise CompositeError(65, 'checkpoint already consumed; inspect its recorded resume attempt')
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return data
