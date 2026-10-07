"""Bounded composition with fresh conditions and durable stage-start records.

This orchestrates declared native tasks, not model-generated cross-stage plans.
An interrupted STARTED stage has unknown ownership: receipts never authorize
automatic replay or resumption. Native episodes remain independent records.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid


class CompositeError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def point(value):
    return (type(value) is list and len(value) == 3 and
            all(type(x) in (int, float) and math.isfinite(x) for x in value))


def clean(value):
    """Only receipt representation changes; native raw evidence is preserved."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return None if type(value) is float and not math.isfinite(value) else value


def validate_plan(plan):
    required = {'scenario_id', 'initial_objects', 'stages', 'final_empty_positions',
                'position_tolerance_m', 'clearance_m', 'motion_profile_id'}
    if type(plan) is not dict or set(plan) != required:
        raise CompositeError(60, 'exact plan fields required')
    for name in ('scenario_id', 'motion_profile_id'):
        if type(plan[name]) is not str or not plan[name] or len(plan[name]) > 128:
            raise CompositeError(60, 'invalid ' + name)
    for name, lower, upper in [('position_tolerance_m', 0, .06), ('clearance_m', .05, .25)]:
        v = plan[name]
        if type(v) not in (int, float) or not math.isfinite(v) or v > upper or (v <= lower if lower == 0 else v < lower):
            raise CompositeError(60, 'invalid ' + name)
    objects = plan['initial_objects']
    if type(objects) is not dict or not 1 <= len(objects) <= 8 or not all(
            type(k) is str and 0 < len(k) <= 128 and point(v) for k, v in objects.items()):
        raise CompositeError(60, 'invalid initial object positions')
    stages = plan['stages']
    if type(stages) is not list or not 1 <= len(stages) <= 8:
        raise CompositeError(60, '1..8 stages required')
    seen = set()
    for stage in stages:
        if type(stage) is not dict or set(stage) != {'stage_id', 'object_name', 'destination'}:
            raise CompositeError(60, 'invalid stage fields')
        sid = stage['stage_id']
        if type(sid) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', sid) or sid in seen:
            raise CompositeError(60, 'stage IDs must be unique')
        if type(stage['object_name']) is not str or stage['object_name'] not in objects or not point(stage['destination']):
            raise CompositeError(60, 'undeclared object or invalid destination')
        seen.add(sid)
    empties = plan['final_empty_positions']
    if type(empties) is not list or len(empties) > 8 or not all(point(p) for p in empties):
        raise CompositeError(60, 'invalid empty positions')
    return copy.deepcopy(plan)



def prepare_plan(plan):
    """Reject contradictions in the declared chain before any observation/motion.

    These are center-position conditions only. Fresh observations, IK and the
    existing native skill gates still decide whether execution can proceed.
    """
    plan=validate_plan(plan);expected=copy.deepcopy(plan['initial_objects'])
    for stage in plan['stages']:
        if not vacant(expected,stage['destination'],plan['clearance_m'],stage['object_name']):
            raise CompositeError(60,'declared destination occupied at '+stage['stage_id'])
        expected[stage['object_name']]=list(stage['destination'])
    if not all(vacant(expected,p,plan['clearance_m']) for p in plan['final_empty_positions']):
        raise CompositeError(60,'declared final empty position conflicts with the chain')
    return plan


def positions(observation, names):
    carry = observation.get('carry') if type(observation) is dict else None
    if (type(observation) is not dict or type(observation.get('outcome')) is not int or observation['outcome'] != 0
            or type(observation.get('error_code')) is not int or observation['error_code'] != 0
            or observation.get('source') != 'SIMULATION_GROUND_TRUTH'
            or type(observation.get('revision')) is not int or observation['revision'] < 0
            or not observation.get('evidence_id')
            or type(carry) is not dict or carry.get('engaged') is not False or carry.get('object_id') != ''):
        raise CompositeError(64, 'fresh observation or released carry unconfirmed')
    objects = observation.get('objects')
    if type(objects) is not list or any(type(o) is not dict for o in objects):
        raise CompositeError(64, 'invalid observed objects')
    result = {}
    for obj in objects:
        name = obj.get('name')
        if type(name) is not str or name in result or obj.get('available') is not True or not point(obj.get('position')):
            raise CompositeError(64, 'missing, duplicate or invalid observed object')
        result[name] = obj['position']
    if set(result) != set(names):
        raise CompositeError(64, 'plan must declare every observed object')
    return result


def matches(actual, expected, tolerance):
    return all(math.dist(actual[name], xyz) <= tolerance for name, xyz in expected.items())


def vacant(actual, destination, clearance, moving=None):
    return all(math.dist(xyz, destination) > clearance for name, xyz in actual.items() if name != moving)


def native_success(component, goal_uuid, tolerance):
    if type(component) is not dict:
        return False
    final = component.get('final_state') or {}
    error = component.get('final_position_error_m')
    final_error = final.get('final_position_error_m')
    return (component.get('terminal_status') == 'SUCCEEDED'
            and type(component.get('outcome')) is int and component['outcome'] == 0
            and type(component.get('error_code')) is int and component['error_code'] == 0
            and type(component.get('run_id')) is str and bool(component['run_id'])
            and type(component.get('episode_path')) is str and bool(component['episode_path'])
            and component.get('goal_uuid') == final.get('goal_uuid') == goal_uuid
            and (type(final.get('outcome')) is str and final['outcome'] == '0'
                 or type(final.get('outcome')) is int and final['outcome'] == 0)
            and type(final.get('error_code')) is int and final['error_code'] == 0
            and component.get('object_at_place') is True and final.get('object_at_place') is True
            and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= tolerance for v in (error, final_error)))


class Journal:
    """Exclusive parent receipt; fsync before handing a stage to the executor."""
    def __init__(self, directory, run_id, context):
        root = Path(directory).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / (run_id + '.jsonl')
        self.file = self.path.open('x', encoding='utf-8')
        self.context = dict(context, run_id=run_id, record_kind='ACTUAL_COMPOSITE_TASK')
        self.seq = 0

    def emit(self, event, **data):
        line = json.dumps(clean(dict(self.context, seq=self.seq, event=event, **data)), sort_keys=True, allow_nan=False)
        self.file.write(line + '\n')
        self.file.flush()
        os.fsync(self.file.fileno())
        self.seq += 1

    def close(self):
        self.file.close()


def execute(plan, observe, native, emit, cancelled=lambda: False, pause_after_stages=0, checkpoint=None):
    completed, components, goal_ids = [], [], []
    def terminal(outcome, code, detail):
        result = dict(outcome=outcome, error_code=code, detail=detail,
                      completed_stage_ids=list(completed), component_run_ids=list(components), component_goal_uuids=list(goal_ids))
        emit('TERMINAL', **result)
        return result
    def check_cancel():
        if cancelled():
            raise CompositeError(32, 'canceled; no subsequent stage dispatched')
    try:
        plan = prepare_plan(plan)
        if type(pause_after_stages) is not int or not 0 <= pause_after_stages < len(plan['stages']):
            raise CompositeError(60, 'pause must be zero or a proper committed prefix')
        if checkpoint is not None and pause_after_stages:
            raise CompositeError(65, 'resume must finish the remaining chain')
        emit('PLAN', plan=plan, plan_sha256=hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(), pause_after_stages=pause_after_stages)
        expected = copy.deepcopy(plan['initial_objects'])
        inherited = 0
        if checkpoint is not None:
            inherited = len(checkpoint['completed_stage_ids'])
            if not 0 < inherited < len(plan['stages']) or checkpoint['completed_stage_ids'] != [s['stage_id'] for s in plan['stages'][:inherited]]:
                raise CompositeError(65, 'checkpoint prefix does not match plan')
            completed.extend(checkpoint['completed_stage_ids']); components.extend(checkpoint['component_run_ids']); goal_ids.extend(checkpoint['component_goal_uuids'])
            expected = copy.deepcopy(checkpoint['expected_positions'])
            emit('RESUME', checkpoint=checkpoint)
        tolerance, clearance = plan['position_tolerance_m'], plan['clearance_m']
        def snapshot(stage, boundary):
            check_cancel()
            observation = observe(stage, boundary)
            emit('OBSERVATION', stage_id=stage, boundary=boundary, observation=observation)
            check_cancel()
            return positions(observation, expected)
        for stage in plan['stages'][inherited:]:
            sid, name, dest = stage['stage_id'], stage['object_name'], stage['destination']
            actual = snapshot(sid, 'before')
            if not matches(actual, expected, tolerance) or not vacant(actual, dest, clearance, name):
                raise CompositeError(61, 'state drift or occupied destination before ' + sid)
            check_cancel()
            goal_uuid = uuid.uuid4().hex
            emit('STARTED', stage_id=sid, component_goal_uuid=goal_uuid)
            component = native(stage, goal_uuid)
            emit('NATIVE_TERMINAL', stage_id=sid, component=component)
            if type(component) is dict and component.get('run_id'):
                components.append(component['run_id']); goal_ids.append(goal_uuid)
            check_cancel()
            if not native_success(component, goal_uuid, tolerance) or len(set(components)) != len(components):
                raise CompositeError(62, 'native terminal/verification unconfirmed for ' + sid)
            expected[name] = list(dest)
            actual = snapshot(sid, 'after')
            if not matches(actual, expected, tolerance):
                raise CompositeError(63, 'measured postcondition failed for ' + sid)
            completed.append(sid)
            emit('COMMITTED', stage_id=sid, component_run_id=component['run_id'], expected_positions=expected)
            if pause_after_stages and len(completed) == pause_after_stages:
                return terminal(3, 0, 'requested committed prefix measured; explicit resume required')
        actual = snapshot('', 'final')
        if not matches(actual, expected, tolerance) or not all(vacant(actual, dest, clearance) for dest in plan['final_empty_positions']):
            raise CompositeError(63, 'joint final positions or empty-space condition failed')
        check_cancel()
        return terminal(0, 0, 'all native stages and fresh joint conditions confirmed')
    except CompositeError as exc:
        return terminal(2 if exc.code == 32 else 1, exc.code, str(exc))
    except Exception as exc:
        return terminal(1, 2, type(exc).__name__ + ': ' + str(exc))
