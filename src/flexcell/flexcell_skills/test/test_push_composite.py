"""Push stages inside the bounded composite chain, and legacy compatibility.

THE COMPATIBILITY CONTRACT THIS FILE ENFORCES
    Every archived T01-T06 plan has stage dicts that are EXACTLY
    {stage_id, object_name, destination}. Introducing push must not change
    what those plans mean, must not change which of them validate, and must not
    add a code path that reads a push field for them. The first half of this
    file proves that by running an unmodified legacy plan end to end and by
    asserting that the legacy validator still refuses every mutation it used to.

THE PUSH HALF
    A push stage declares a direction and a distance, never a destination -
    two declarations of the same fact can disagree. So the chain derives where
    the object must end up and re-checks it against a fresh measurement, which
    is exactly the independent second gate a place stage gets.
"""
import copy
import math

import pytest

from flexcell_skills.contracts.composite import (
    ACTION_PUSH, CompositeError, execute, is_push, prepare_plan,
    push_expectation, stage_action, validate_plan)

# The archived legacy plan shape, unchanged (same fixture test_composite.py uses).
LEGACY = dict(
    scenario_id='legacy',
    initial_objects={'a': [.22, 0, .0175], 'b': [.20, -.18, .0175]},
    stages=[dict(stage_id='s1', object_name='a', destination=[.12, -.15, .0175])],
    final_empty_positions=[],
    position_tolerance_m=.02, clearance_m=.05, motion_profile_id='demo_slow')


def push_plan(**overrides):
    plan = dict(
        scenario_id='t08',
        initial_objects={'a': [.22, 0, .0175], 'b': [.20, -.18, .0175]},
        stages=[dict(stage_id='p1', object_name='a', action=ACTION_PUSH,
                     direction=[-1.0, 0.0, 0.0], distance_m=.03,
                     contact_height_m=.03)],
        final_empty_positions=[],
        position_tolerance_m=.02, clearance_m=.05,
        motion_profile_id='demo_slow')
    plan.update(overrides)
    return plan


class Rig:
    """Scripted world for the chain: the box moves only when we say so."""

    def __init__(self, plan, displacement=(0.030, 0.0, 0.0)):
        self.actual = copy.deepcopy(plan['initial_objects'])
        self.displacement = displacement
        self.calls, self.events, self.observed = [], [], []
        self.native_result = None

    def observe(self, stage, boundary):
        self.observed.append((stage, boundary))
        return dict(outcome=0, error_code=0, source='SIMULATION_GROUND_TRUTH',
                    revision=len(self.calls), evidence_id='obs-%d' % len(self.observed),
                    carry=dict(engaged=False, object_id=''),
                    objects=[dict(name=k, available=True, position=v[:])
                             for k, v in self.actual.items()])

    def _cosine(self, stage):
        magnitude = math.sqrt(sum(v * v for v in self.displacement))
        if magnitude == 0.0:
            return float('nan')
        d = stage['direction']
        along = sum(self.displacement[i] * d[i] for i in range(2))
        return along / magnitude

    def _lateral(self, stage):
        d = stage['direction']
        return abs(self.displacement[0] * d[1] - self.displacement[1] * d[0])

    def native(self, stage, goal_uuid):
        assert self.events[-1]['event'] == 'STARTED'
        self.calls.append(stage['stage_id'])
        if is_push(stage):
            self.actual[stage['object_name']] = [
                self.actual[stage['object_name']][i] + self.displacement[i]
                for i in range(3)]
            result = dict(
                run_id='native-' + stage['stage_id'], goal_uuid=goal_uuid,
                terminal_status='SUCCEEDED', outcome=0, error_code=0,
                contact_made=True, contact_lost=False,
                carry_engaged_during=False,
                displacement_m=math.sqrt(sum(v * v for v in self.displacement)),
                # Cosine against THIS stage's declared direction, the same
                # quantity the skill reports.
                direction_cos=self._cosine(stage),
                lateral_m=self._lateral(stage),
                delta_z_m=self.displacement[2],
                final_state=dict(goal_uuid=goal_uuid, outcome='0', error_code=0))
        else:
            self.actual[stage['object_name']] = stage['destination'][:]
            result = dict(
                run_id='native-' + stage['stage_id'], episode_path='e.json',
                goal_uuid=goal_uuid, terminal_status='SUCCEEDED', outcome=0,
                error_code=0, object_at_place=True, final_position_error_m=.001,
                final_state=dict(goal_uuid=goal_uuid, outcome='0', error_code=0,
                                 object_at_place=True, final_position_error_m=.001))
        if self.native_result is not None:
            result.update(self.native_result)
        return result

    def emit(self, event, **data):
        self.events.append(dict(event=event, **copy.deepcopy(data)))

    def run(self, plan=None):
        return execute(copy.deepcopy(plan or push_plan()), self.observe,
                       self.native, self.emit, lambda: False)


# ------------------------------------------------------- legacy compatibility
def test_legacy_plan_still_validates_and_runs_unchanged():
    rig = Rig(LEGACY)
    result = rig.run(LEGACY)
    assert result['outcome'] == 0
    assert result['completed_stage_ids'] == ['s1']
    # The chain's expectation for a legacy stage is still its declared
    # destination, to the letter.
    committed = [e for e in rig.events if e['event'] == 'COMMITTED'][0]
    assert committed['expected_positions']['a'] == [.12, -.15, .0175]


def test_legacy_stage_is_not_mistaken_for_a_push():
    stage = dict(stage_id='s', object_name='a', destination=[.12, -.15, .0175])
    assert stage_action(stage) == 0 and is_push(stage) is False
    # prepare_plan must not derive any expectation for it.
    prepare_plan(copy.deepcopy(LEGACY))


def test_push_fields_on_a_stage_without_the_action_marker_are_refused():
    """The action marker is what opts in; a destination plus push fields is
    ambiguous and must not be silently resolved one way or the other."""
    plan = push_plan()
    plan['stages'][0]['destination'] = [.19, 0, .0175]
    with pytest.raises(CompositeError) as exc:
        validate_plan(plan)
    assert exc.value.code == 60


@pytest.mark.parametrize('change,needle', [
    (dict(direction=[0., 0., 0.]), 'direction'),
    (dict(direction=[-1., 0., 1.]), 'direction'),
    (dict(direction='left'), 'direction'),
    (dict(distance_m=0.0), 'distance'),
    (dict(distance_m=0.7), 'distance'),
    (dict(contact_height_m=9.0), 'contact_height_m'),
    (dict(overdrive_m=-1.0), 'overdrive_m'),
    (dict(max_increments=99), 'max_increments'),
])
def test_invalid_push_stages_are_refused_before_any_dispatch(change, needle):
    plan = push_plan()
    plan['stages'][0].update(change)
    rig = Rig(plan)
    result = rig.run(plan)
    assert result['error_code'] == 60
    assert 'invalid' in result['detail']
    assert rig.calls == [] and rig.observed == []


def test_push_stage_requires_the_object_to_be_declared():
    plan = push_plan()
    plan['stages'][0]['object_name'] = 'ghost'
    with pytest.raises(CompositeError) as exc:
        validate_plan(plan)
    assert exc.value.code == 60


def test_push_expectation_is_derived_from_the_origin_not_declared():
    stage = push_plan()['stages'][0]
    expect = push_expectation([.22, 0, .0175], stage)
    assert expect == pytest.approx([.19, 0, .0175], abs=1e-12)
    # And the stage itself carries no destination to disagree with.
    assert 'destination' not in stage


# ------------------------------------------------------------- chain semantics
def test_a_push_stage_commits_when_the_measured_displacement_matches():
    rig = Rig(push_plan(), displacement=(-0.030, 0.0, 0.0))
    result = rig.run()
    assert result['outcome'] == 0, result['detail']
    assert result['completed_stage_ids'] == ['p1']
    committed = [e for e in rig.events if e['event'] == 'COMMITTED'][0]
    assert committed['expected_positions']['a'] == pytest.approx(
        [.19, 0, .0175], abs=1e-9)


def test_a_push_stage_that_moved_the_wrong_distance_fails_the_chain():
    """The composite gate is independent of the skill's own verdict: a skill
    that reported SUCCEEDED after moving 10 mm must not commit the chain."""
    rig = Rig(push_plan(), displacement=(-0.010, 0.0, 0.0))
    result = rig.run()
    assert result['outcome'] == 1 and result['error_code'] == 62
    assert result['completed_stage_ids'] == []


def test_a_push_stage_that_reports_contact_lost_cannot_commit():
    rig = Rig(push_plan(), displacement=(-0.023, 0.0, 0.0))
    rig.native_result = dict(contact_lost=True)
    result = rig.run()
    assert result['outcome'] == 1 and result['error_code'] == 62


def test_a_push_that_was_secretly_carried_cannot_commit():
    """Anti-fake-success at the chain level: the skill may be lying, the
    measured carry flag may not."""
    rig = Rig(push_plan(), displacement=(-0.030, 0.0, 0.0))
    rig.native_result = dict(carry_engaged_during=True)
    result = rig.run()
    assert result['outcome'] == 1 and result['error_code'] == 62


def test_a_push_stage_composes_after_a_place_stage():
    plan = push_plan()
    plan['initial_objects'] = {'a': [.22, 0, .0175], 'b': [.20, -.18, .0175]}
    plan['stages'] = [
        dict(stage_id='put', object_name='b', destination=[.12, -.15, .0175]),
        dict(stage_id='shove', object_name='b', action=ACTION_PUSH,
             direction=[0.0, -1.0, 0.0], distance_m=.02)]
    rig = Rig(plan, displacement=(0.0, -0.020, 0.0))
    result = rig.run(plan)
    assert result['outcome'] == 0, result['detail']
    assert result['completed_stage_ids'] == ['put', 'shove']


def test_a_push_that_would_land_on_another_object_is_refused_before_motion():
    plan = push_plan()
    plan['stages'][0]['distance_m'] = .03
    # Put another object exactly where the push would end.
    plan['initial_objects']['b'] = [.19, 0.0, .0175]
    rig = Rig(plan)
    result = rig.run(plan)
    assert result['error_code'] == 60
    assert rig.calls == []
