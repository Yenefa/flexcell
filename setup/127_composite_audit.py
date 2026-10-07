#!/usr/bin/env python3
"""Read-only joint-state, parent/component identity and routing audit."""
import argparse
import hashlib
import json
from pathlib import Path

from flexcell_skills.contracts.composite import matches, native_success, positions, vacant, validate_plan
from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.contracts.episode import _sanitize
from flexcell_skills.contracts.receipt_json import loads, same_typed


def require(value, detail):
    if not value:
        raise ValueError(detail)


def audit(receipt, episodes, deployment):
    events = [loads(line) for line in Path(receipt).read_text().splitlines()]
    require(bool(events), 'empty receipt')
    first = events[0]
    identity = ['record_kind', 'run_id', 'goal_uuid', 'runtime_fingerprint', 'policy', 'policy_version']
    for seq, event in enumerate(events):
        require(type(event['seq']) is int and event['seq'] == seq and all(event[k] == first[k] for k in identity), 'journal identity/sequence mismatch')
    require(first['record_kind'] == 'ACTUAL_COMPOSITE_TASK' and first['runtime_fingerprint'] == deployment['runtime_fingerprint'], 'parent/deployment mismatch')
    require(events[-1]['event'] == 'TERMINAL' and not any(e['event'] == 'TERMINAL' for e in events[:-1]), 'terminal receipt unconfirmed')
    terminal = events[-1]
    require(type(terminal['outcome']) is int and terminal['outcome'] == 0 and type(terminal['error_code']) is int and terminal['error_code'] == 0, 'parent failed; receipt retained')
    require(first['event'] == 'PLAN', 'registered plan missing')
    plan = validate_plan(first['plan']); expected = dict(plan['initial_objects'])
    require(first['plan_sha256'] == hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(), 'plan digest mismatch')
    tol, clearance = plan['position_tolerance_m'], plan['clearance_m']
    cursor, run_ids, goal_ids, stage_ids, routing = 1, [], [], [], []
    for stage in plan['stages']:
        sid = stage['stage_id']
        segment = events[cursor:cursor + 5]
        require([e['event'] for e in segment] == ['OBSERVATION','STARTED','NATIVE_TERMINAL','OBSERVATION','COMMITTED'], 'stage sequence mismatch')
        require(all(e['stage_id'] == sid for e in segment), 'cross-stage receipt mismatch')
        pre, start, native, post, committed = segment
        require(pre['boundary'] == 'before' and post['boundary'] == 'after', 'observation boundaries mismatch')
        actual = positions(pre['observation'], expected)
        require(matches(actual, expected, tol) and vacant(actual, stage['destination'], clearance, stage['object_name']), 'precondition failed')
        component = native['component']; goal_uuid = start['component_goal_uuid']
        require(native_success(component, goal_uuid, tol), 'unconfirmed native terminal')
        candidates = list(Path(episodes).glob('*_' + component['run_id'] + '.json'))
        exact = Path(episodes) / (component['run_id'] + '.json')
        if exact.is_file(): candidates.append(exact)
        require(len(candidates) == 1, 'exactly one persisted component episode required')
        episode = loads(candidates[0].read_text())
        require(episode['runtime_fingerprint'] == first['runtime_fingerprint'] and episode['run_id'] == component['run_id'], 'component identity mismatch')
        final = episode['final_state']
        # EpisodeRecorder freezes floats to nine decimals. Compare that exact
        # representation; native_success still checks unrounded finite errors.
        require(same_typed(final, _sanitize(component['final_state'])), 'native final state differs from recorded component')
        require(final['parent_run_id'] == first['run_id'] and final['stage_id'] == sid
                and final['execution_kind'] == 'IN_PROCESS_COMPONENT' and final['component_execution_id'] == goal_uuid,
                'internal execution correlation mismatch')
        require(all(s['policy_input']['goal']['assignments'] == [[stage['object_name'],'task_place']] for s in episode['steps']), 'native target mismatch')
        for action in ('PICK','PLACE','VERIFY'):
            require(any(s['policy_output']['action'] == action and s['policy_output']['target'] == stage['object_name']
                        and type((s.get('executor_result') or {}).get('outcome')) is int
                        and s['executor_result']['outcome'] == 0 for s in episode['steps']), 'missing successful '+action)
        if first['policy'] == 'hybrid':
            route = audit_routing_episode(episode, deployment); require(route['ok'], 'routing failed'); routing.append(route)
        expected[stage['object_name']] = stage['destination']
        require(matches(positions(post['observation'], expected), expected, tol), 'postcondition failed')
        require(committed['expected_positions'] == expected and committed['component_run_id'] == component['run_id'], 'commit evidence mismatch')
        stage_ids.append(sid); run_ids.append(component['run_id']); goal_ids.append(goal_uuid); cursor += 5
    require(len(set(run_ids)) == len(run_ids) and len(set(goal_ids)) == len(goal_ids), 'repeated component identity')
    require(cursor == len(events)-2, 'unexpected trailing events')
    final = events[cursor]
    require(final['event'] == 'OBSERVATION' and final['boundary'] == 'final' and final['stage_id'] == '', 'fresh joint final observation missing')
    actual = positions(final['observation'], expected)
    require(matches(actual, expected, tol) and all(vacant(actual, dest, clearance) for dest in plan['final_empty_positions']), 'joint final predicate failed')
    require(terminal['completed_stage_ids'] == stage_ids and terminal['component_run_ids'] == run_ids and terminal['component_goal_uuids'] == goal_ids, 'terminal progress mismatch')
    return dict(ok=True, schema_version=2, serialization='EpisodeRecorder._sanitize (nine decimal places)',
                run_id=first['run_id'], runtime_fingerprint=first['runtime_fingerprint'],
                completed_stage_ids=stage_ids, component_run_ids=run_ids, observations=2*len(stage_ids)+1, routing=routing,
                final_positions=actual, physical_safety='NOT_RUN', qualification='FROZEN',
                correlation='components run in-process; their UUIDs are internal execution IDs, not accepted DDS action goals')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--receipt', required=True, type=Path)
    ap.add_argument('--episodes', required=True, type=Path)
    ap.add_argument('--deployment', required=True, type=Path)
    args = ap.parse_args()
    try:
        result = audit(args.receipt, args.episodes, loads(args.deployment.read_text()))
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=type(exc).__name__+': '+str(exc))))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
