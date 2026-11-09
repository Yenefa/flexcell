"""Deterministic safety gate between policy and executor (M2.1-5, issue #6).

Implements the §2.6 validator, BEFORE dispatch.  The executor asks the policy
WHAT to do (ADR-002); this gate decides whether the proposal is IN CONTRACT
before any skill goal is built.  The gate is a pure function of the
policy-facing view (the canonical WorldState envelope dict - gz ground truth,
not the planning-scene belief), the task goal, the constraints, and the
proposal itself.  Rejection is deterministic: same inputs, same verdict.

Rejection reasons (all typed, recorded with the FULL decision object):
  action_not_allowed  - decision.action not in constraints.allowed_actions
                        (B2/B3: the executor owns the action menu)
  unknown_target      - decision.target is not one of the task assignments
  world_required      - the decision needs world state but none exists yet
  world_stale         - freshest object pose_age_s exceeds the constraint
                        (STALE_WORLD emission point, error_codes ERR_STALE_WORLD)
  target_not_available - PICK: object missing/unavailable in the world
  already_carried     - PICK: something is already carried
  not_carried         - PLACE: the target object is not the carried one

`explanation` (policy free text) NEVER passes the gate: `sanitize()` returns
the dispatch-facing fields only - free text is logged, never parsed, never
forwarded (ADR-002).

Counting is the EXECUTOR's job (B2/B3): the gate returns the verdict, the
executor accounts evaluated/rejected and exposes invalid-decisions-per-1000.
"""

import math

STALE_WORLD = 'world_stale'
SAFETY_REJECTED = 'safety_rejected'


def sanitize(decision):
    """Dispatch-facing view of a decision: no free text survives."""
    return {"action": decision.action, "target": decision.target}


def validate(decision, goal, world_dict, constraints, history=None):
    """Validate a policy proposal.  Returns (ok, reason).

    ok=True  -> the proposal is in contract; dispatch may proceed.
    ok=False -> reason is one of the typed rejection reasons above; the
                executor must NOT dispatch and must record the rejection.
    world_dict: the parsed canonical WorldState envelope (or None when no
    observe has happened yet).
    """
    # 1) action menu is executor-owned (B2/B3)
    if decision.action not in constraints.allowed_actions:
        return False, 'action_not_allowed'

    # 2) target must be one of the task's assignment objects
    known = {obj for obj, _zone in goal.assignments}
    if decision.action in ('OBSERVE', 'PICK', 'PLACE', 'VERIFY'):
        if decision.target not in known:
            return False, 'unknown_target'

    if decision.action in ('WAIT', 'ABORT'):
        return True, None
    if decision.action == 'OBSERVE':
        # OBSERVE produces the world - it is the one state-consuming-looking
        # action that MUST be allowed pre-world (leg start has no world yet)
        return True, None

    # 3) actions that consume world facts need a world at all
    if world_dict is None:
        return False, 'world_required'

    ws = world_dict.get('world_state', {})
    objects = {o.get('name'): o for o in ws.get('objects', [])}
    carry = ws.get('carry', {})

    # 4) world freshness gate (STALE_WORLD emission point)
    if constraints.max_world_age_s > 0:
        ages = [float(o.get('pose_age_s') or 0.0)
                for o in objects.values() if o.get('available')]
        if ages and max(ages) > constraints.max_world_age_s:
            return False, STALE_WORLD

    # 5) PICK: object available (gz truth, not backend belief) and nothing
    #    else already carried
    if decision.action == 'PICK':
        obj = objects.get(decision.target)
        if obj is None or not obj.get('available'):
            return False, 'target_not_available'
        if carry.get('engaged'):
            return False, 'already_carried'

    # 6) PLACE: the target object must be the carried one
    if decision.action == 'PLACE':
        if not carry.get('engaged') or carry.get('object_id') != decision.target:
            return False, 'not_carried'

    # 7) action ORDER (P1-C): a legal-looking decision is still out of order
    #    when its own history does not support it. Without this a policy could
    #    PLACE an object it never picked, or VERIFY one it never placed.
    if history is not None:
        ok, reason = _order_ok(decision, tuple(history))
        if not ok:
            return False, reason

    return True, None


def _order_ok(decision, history):
    """Precondition check against the executor-recorded history.

    Typed reasons:
      place_without_pick   - PLACE for an object whose PICK never succeeded
      verify_without_place - VERIFY for an object whose PLACE never succeeded
      pick_while_carried   - PICK while this task already carries an object
    """
    action, target = decision.action, decision.target
    if action == 'PLACE':
        if not any(h.action == 'PICK' and h.target == target and h.outcome == 0
                   for h in history):
            return False, 'place_without_pick'
    elif action == 'VERIFY':
        placed = any(h.action == 'PLACE' and h.target == target and h.outcome == 0
                     for h in history)
        # The resume shortcut may verify an object that a PREVIOUS session left
        # at its goal (the executor accepted it through the resume receipt), so
        # a successful OBSERVE for that target also justifies the check.
        observed = any(h.action == 'OBSERVE' and h.outcome == 0 for h in history)
        if not placed and not observed:
            return False, 'verify_without_place'
    elif action == 'PICK':
        for h in reversed(history):
            if h.action == 'PLACE' and h.outcome == 0:
                break
            if h.action == 'PICK' and h.target == target and h.outcome == 0:
                return False, 'pick_while_carried'
    return True, None


def destination_clear(world_dict, target, destination):
    """Conservative pre-PICK check against the observed boxes.

    The carried box can rotate en route: bound it by its circumscribed sphere
    and test that sphere against each passive box in the box's measured frame.
    This checks destination occupancy only; MoveIt still plans the motion.
    Missing or invalid geometry cannot establish a free destination.
    """
    def vector(value, length):
        values = tuple(float(v) for v in value)
        if len(values) != length or not all(math.isfinite(v) for v in values):
            raise ValueError('invalid geometry')
        return values

    def size_of(obj):
        if obj['klass'] != 'box' or not obj['available']:
            raise ValueError('unavailable box')
        size = vector(obj['size'], 3)
        if min(size) <= 0:
            raise ValueError('invalid box size')
        return size

    try:
        objects = world_dict['world_state']['objects']
        moving = next(obj for obj in objects if obj['name'] == target)
        radius = math.hypot(*size_of(moving)) / 2
        goal = vector(destination, 3)
        for obj in objects:
            if obj['name'] == target:
                continue
            half = tuple(s / 2 for s in size_of(obj))
            pose = obj['pose']
            center = vector((pose['position'][k] for k in 'xyz'), 3)
            x, y, z, w = vector((pose['orientation'][k] for k in 'xyzw'), 4)
            norm = math.hypot(x, y, z, w)
            if abs(norm - 1.0) > .001:
                raise ValueError('invalid quaternion')
            x, y, z, w = (v / norm for v in (x, y, z, w))
            # Columns of the rotation matrix map world deltas into box axes.
            axes = ((1 - 2*(y*y + z*z), 2*(x*y + z*w), 2*(x*z - y*w)),
                    (2*(x*y - z*w), 1 - 2*(x*x + z*z), 2*(y*z + x*w)),
                    (2*(x*z + y*w), 2*(y*z - x*w), 1 - 2*(x*x + y*y)))
            delta = tuple(g - c for g, c in zip(goal, center))
            outside = [max(0.0, abs(sum(a*d for a, d in zip(axis, delta))) - h)
                       for axis, h in zip(axes, half)]
            if math.hypot(*outside) <= radius:
                return False, 'destination_occupied:' + obj['name']
    except (KeyError, TypeError, ValueError, StopIteration, OverflowError):
        return False, 'destination_geometry_unavailable'
    return True, None


def rejection_canonical_code(reason):
    """Typed canonical code for a rejection (error_codes vocabulary)."""
    from flexcell_skills.contracts.error_codes import (
        ERR_INTERNAL, ERR_INVALID_GOAL, ERR_OBJECT_NOT_FOUND, ERR_NOT_CARRIED,
        ERR_SAFETY_REJECTED, ERR_STALE_WORLD)
    return {
        'action_not_allowed': ERR_SAFETY_REJECTED,
        'unknown_target': ERR_INVALID_GOAL,
        'world_required': ERR_STALE_WORLD,
        STALE_WORLD: ERR_STALE_WORLD,
        'target_not_available': ERR_OBJECT_NOT_FOUND,
        'already_carried': ERR_SAFETY_REJECTED,
        'not_carried': ERR_NOT_CARRIED,
        'place_without_pick': ERR_SAFETY_REJECTED,
        'verify_without_place': ERR_SAFETY_REJECTED,
        'pick_while_carried': ERR_SAFETY_REJECTED,
        'destination_occupied': ERR_SAFETY_REJECTED,
        'destination_geometry_unavailable': ERR_SAFETY_REJECTED,
    }.get((reason or '').split(':', 1)[0], ERR_INTERNAL)


def metrics(evaluated, rejected):
    """invalid-decisions-per-1000 accounting (executor feeds the counters)."""
    return {
        "evaluated": int(evaluated),
        "rejected": int(rejected),
        "invalid_per_1000": (round(1000.0 * rejected / evaluated, 3)
                             if evaluated else 0.0),
    }
