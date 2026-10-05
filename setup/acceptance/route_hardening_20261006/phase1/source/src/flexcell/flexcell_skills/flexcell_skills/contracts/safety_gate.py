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

STALE_WORLD = 'world_stale'
SAFETY_REJECTED = 'safety_rejected'


def sanitize(decision):
    """Dispatch-facing view of a decision: no free text survives."""
    return {"action": decision.action, "target": decision.target}


def validate(decision, goal, world_dict, constraints):
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
    }.get(reason, ERR_INTERNAL)


def metrics(evaluated, rejected):
    """invalid-decisions-per-1000 accounting (executor feeds the counters)."""
    return {
        "evaluated": int(evaluated),
        "rejected": int(rejected),
        "invalid_per_1000": (round(1000.0 * rejected / evaluated, 3)
                             if evaluated else 0.0),
    }
