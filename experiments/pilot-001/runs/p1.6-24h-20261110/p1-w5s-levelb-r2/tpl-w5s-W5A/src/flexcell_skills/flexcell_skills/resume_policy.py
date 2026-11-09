"""Opt-in verified completion shortcuts shared by every decision policy.

An observation only proposes VERIFY. Only a successful independent verifier
removes an assignment; recorded history and canonical world bytes stay intact.
"""
from dataclasses import replace
import json
import math

from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.decision_policy import (
    ACTION_ABORT, ACTION_OBSERVE, ACTION_PICK, ACTION_VERIFY, Decision,
    DecisionPolicy, RC_PLAN_NEXT, RC_VERIFY_BUDGET_EXHAUSTED)


class ResumePolicy(DecisionPolicy):
    def __init__(self, policy):
        self._policy = policy
        self.name = policy.name + '+resume'
        self.version = policy.version + '+1'

    def decide(self, world, goal, constraints, history):
        completed = {h.target for h in history if h.action == ACTION_VERIFY and h.outcome == 0}
        remaining = tuple(a for a in goal.assignments if a[0] not in completed)
        # The executor owns task completion and never calls us after this point.
        if not remaining:
            raise ValueError('all assignments already verified')
        scoped = tuple(h for h in history if h.target not in completed)
        target, zone = remaining[0]
        leg = [h for h in scoped if h.target == target]
        probes = []
        for h in leg:
            if h.action == ACTION_PICK:
                break
            if h.action == ACTION_VERIFY:
                probes.append(h)
        if probes:
            if sum(h.action == ACTION_VERIFY for h in leg) >= 1 + constraints.recovery_budget:
                return Decision(ACTION_ABORT, target, reason_code=RC_VERIFY_BUDGET_EXHAUSTED,
                                explanation='completion check failed and verifier budget is exhausted')
            # A failed initial check starts a normal leg with a fresh OBSERVE.
            # This is a view for the delegate, not a rewrite of recorded history.
            last_probe = max(i for i, h in enumerate(scoped) if h is probes[-1])
            scoped = tuple(h for i, h in enumerate(scoped) if h.target != target or i > last_probe)
            if not any(h.target == target for h in scoped):
                return Decision(ACTION_OBSERVE, target, reason_code=RC_PLAN_NEXT,
                                explanation='completion check failed; refresh before continuing',
                                policy_trace={'source': 'completion_check', 'fallback': False})
        if (not probes and leg and leg[-1].action == ACTION_OBSERVE and leg[-1].outcome == 0
                and not any(h.action == ACTION_PICK for h in leg)
                and ACTION_VERIFY in constraints.allowed_actions
                and self._at_goal(world, target, zone, constraints)):
            return Decision(ACTION_VERIFY, target, reason_code=RC_PLAN_NEXT,
                            explanation='observed at goal; independently verify before skipping motion',
                            policy_trace={'source': 'completion_check', 'fallback': False})
        return self._policy.decide(world, replace(goal, assignments=remaining), constraints, scoped)

    @staticmethod
    def _at_goal(world, target, zone, constraints):
        if world is None:
            return False
        envelope = world if isinstance(world, dict) else json.loads(serialize_envelope(world))
        state = envelope.get('world_state', {})
        if state.get('carry', {}).get('engaged'):
            return False
        objects = [o for o in state.get('objects', []) if o.get('name') == target]
        zones = [z for z in state.get('zones', []) if z.get('id') == zone]
        if len(objects) != 1 or len(zones) != 1 or objects[0].get('available') is not True:
            return False
        try:
            position = objects[0]['pose']['position']
            center = zones[0]['center']
            values = [position[k] for k in ('x', 'y', 'z')] + [center[k] for k in ('x', 'y', 'z')]
            age = objects[0]['pose_age_s']
            tolerance = constraints.verify_tolerance_m
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in values + [age, tolerance]):
                return False
            if age < 0 or tolerance <= 0 or (constraints.max_world_age_s > 0 and age > constraints.max_world_age_s):
                return False
            return math.dist(values[:3], values[3:]) <= tolerance
        except (KeyError, TypeError):
            return False
