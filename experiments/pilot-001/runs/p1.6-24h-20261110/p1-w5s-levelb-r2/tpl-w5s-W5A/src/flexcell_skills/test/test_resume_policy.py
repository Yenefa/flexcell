"""A pose proposes a check; only measured verification can finish a leg."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock

import pytest

from flexcell_skills.decision_policy import Constraints, FSMPolicy, HistoryRecord, TaskGoal
from flexcell_skills.resume_policy import ResumePolicy


def record(action, target='a', outcome=0, error=0):
    return HistoryRecord(action, target, outcome, error, 1, 1, 'evidence')


def inputs():
    point = dict(x=.12, y=-.15, z=.0175)
    world = {'world_state': {'carry': {'engaged': False}, 'objects': [
        dict(name='a', available=True, pose_age_s=.01, pose={'position': point})],
        'zones': [dict(id='z', center=point)]}}
    goal = TaskGoal('g', 'resume', (('a', 'z'), ('b', 'other')))
    constraints = Constraints(frozenset(('OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'ABORT')), 1, .06, 'demo_slow', .5)
    return world, goal, constraints, (record('OBSERVE'),)


def test_resume_checks_before_skipping_and_delegates_the_actual_remaining_task():
    world, goal, limits, history = inputs()
    original = deepcopy(world)
    policy = ResumePolicy(FSMPolicy())
    assert policy.decide(None, goal, limits, ()).action == 'OBSERVE'
    assert policy.decide(world, goal, limits, history).action == 'VERIFY'
    # Merely issuing VERIFY has not removed anything; its result is required.
    assert policy.decide(world, goal, limits, history).target == 'a'
    next_decision = policy.decide(world, goal, limits, history + (record('VERIFY'),))
    assert (next_decision.action, next_decision.target) == ('OBSERVE', 'b')
    assert world == original and len(goal.assignments) == 2 and len(history) == 1


@pytest.mark.parametrize('defect', ['outside', 'missing', 'unavailable', 'stale', 'nan', 'carried', 'no_zone'])
def test_unusable_or_off_target_observation_never_skips_motion(defect):
    world, goal, limits, history = inputs()
    obj = world['world_state']['objects'][0]
    if defect == 'outside': obj['pose']['position'] = dict(x=.3, y=0, z=.0175)
    elif defect == 'missing': world['world_state']['objects'] = []
    elif defect == 'unavailable': obj['available'] = False
    elif defect == 'stale': obj['pose_age_s'] = 1.
    elif defect == 'nan': obj['pose_age_s'] = float('nan')
    elif defect == 'carried': world['world_state']['carry']['engaged'] = True
    else: world['world_state']['zones'] = []
    assert ResumePolicy(FSMPolicy()).decide(world, goal, limits, history).action == 'PICK'


def test_failed_initial_check_reobserves_then_moves_within_original_budgets():
    world, goal, limits, history = inputs()
    policy = ResumePolicy(FSMPolicy())
    history += (record('VERIFY', outcome=1, error=25),)
    assert policy.decide(world, goal, limits, history).action == 'OBSERVE'
    history += (record('OBSERVE'),)
    assert policy.decide(world, goal, limits, history).action == 'PICK'
    history += (record('PICK'), record('PLACE'))
    assert policy.decide(world, goal, limits, history).action == 'VERIFY'
    history += (record('VERIFY', outcome=1, error=25),)
    decision = policy.decide(world, goal, limits, history)
    assert decision.action == 'ABORT' and decision.reason_code == 'VERIFY_BUDGET_EXHAUSTED'
    assert policy.decide(world, goal, replace(limits, recovery_budget=0), history[:2]).action == 'ABORT'


def test_any_delegate_receives_the_same_world_and_only_independently_verified_legs_are_removed():
    world, goal, limits, history = inputs()
    delegate = Mock(name='policy', version='2')
    delegate.name = 'llm'
    wrapper = ResumePolicy(delegate)
    wrapper.decide(world, goal, limits, history + (record('VERIFY'),))
    args = delegate.decide.call_args.args
    assert args[0] is world and args[1].assignments == (('b', 'other'),)
    assert args[2] is limits and args[3] == ()


def test_failed_check_requires_new_observation_before_any_model_delegate():
    world, goal, limits, history = inputs()
    delegate = Mock(version='2')
    delegate.name = 'llm'
    wrapper = ResumePolicy(delegate)
    history += (record('VERIFY', outcome=1, error=25),)
    assert wrapper.decide(world, goal, limits, history).action == 'OBSERVE'
    delegate.decide.assert_not_called()
    wrapper.decide(world, goal, limits, history + (record('OBSERVE'),))
    assert delegate.decide.call_args.args[3] == (record('OBSERVE'),)
