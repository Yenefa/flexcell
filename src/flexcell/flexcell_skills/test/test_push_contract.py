"""T08 push: goal validation, measured verdict, contact-loss detection.

WHY THESE TESTS LOOK THE WAY THEY DO
    The T08 Step-0 probe measured the exact failure this skill must not miss:
    the box moved 23.02 mm and then stopped, while the end effector advanced a
    further 16 mm. Any implementation that scored "the arm reached its target"
    would call that a success. So the tests below are built around three
    MEASURED scenarios, not around invented ones:

      * run3 (the ceiling): arm arrives, box moves 23.02 mm of 30 mm asked.
      * run2 (the false negative): arm arrives, box does not move at all,
        because the fingers passed 145 mm above it.
      * the saturation replay: the arm keeps advancing and the box does not.

    tests/test_push_probe_evidence.py re-derives those numbers from the
    archived JSONL so these fixtures cannot silently drift from the evidence.

WHAT IS DELIBERATELY NOT ASSERTED
    No success rate, no repeatability, no claim that the physics will behave
    the same on another height or another object. This module tests the
    CONTRACT and the DECISION, not the robot.
"""
import math

import pytest

from flexcell_skills.contracts import push


# --------------------------------------------------------------- fixtures
# Measured by the T08 Step-0 probe (ci-public-window/evidence/
# evobot_t08_push_step0_20261111/run3_z0030/push_step0_summary.json).
BOX_A = [0.220, 0.0, 0.0175]
MEASURED_AFTER_RUN3 = [0.197057, -0.001924, 0.0175]
MEASURED_DISPLACEMENT_RUN3 = 0.023024
MEASURED_COSINE_RUN3 = 0.9965
MEASURED_LATERAL_RUN3 = 0.001924

GOAL = dict(object_name='target_box_a', direction=[-1.0, 0.0, 0.0],
            distance_m=0.030, contact_height_m=0.030, overdrive_m=0.02)


class World:
    """A scripted world: the box moves only while the script says it does.

    This is the whole point of the split. Contact physics is not simulated
    here - the probe already measured it. What is tested is whether the skill
    turns a given sequence of measurements into the right verdict.
    """

    def __init__(self, start, script=None, reach=(True, 0.006), carry=False,
                 cancel_at=None, carry_engaged_at=None, reach_from=None):
        self.position = list(start)
        self.script = list(script or [])
        self.reach = reach
        # reach_from=N: the first N moves succeed, every later one is blocked.
        # Needed because a blocked push and a blocked approach are different
        # failures - one never starts, the other starts and hits something.
        self.reach_from = reach_from
        self.reach_blocked = (False, 0.045)
        self.carry = carry
        self.cancel_at = cancel_at
        self.carry_engaged_at = carry_engaged_at
        self.moves = []
        self.phases = []
        self.events = []
        self.reads = 0

    def measure(self):
        self.reads += 1
        # First read is the pre-push baseline; every later read advances the
        # scripted box by one entry.
        if self.reads > 1 and self.script:
            step = self.script.pop(0)
            self.position = [self.position[i] + step[i] for i in range(3)]
        return list(self.position), None

    def move_to(self, target):
        self.moves.append(list(target))
        if self.cancel_at is not None and len(self.moves) >= self.cancel_at:
            self.cancelled_flag = True
        ok, error = self.reach
        if self.reach_from is not None and len(self.moves) > self.reach_from:
            ok, error = self.reach_blocked
        return ok, error, 'scripted'

    def carry_engaged(self):
        if (self.carry_engaged_at is not None
                and len(self.moves) >= self.carry_engaged_at):
            return True, None
        return self.carry, None

    def cancelled(self):
        return bool(getattr(self, 'cancelled_flag', False))

    def phase(self, name):
        self.phases.append(name)

    def emit(self, event, **data):
        self.events.append(dict(event=event, **data))


def run(world, goal=None, params=None, half=0.0175):
    return push.execute_push(world, dict(goal or GOAL), params or {},
                             half_extent_m=half)


# --------------------------------------------------------- goal validation
@pytest.mark.parametrize('change,needle', [
    (dict(direction=[0., 0., 0.]), 'zero-length'),
    (dict(direction=[-1., 0., 0.5]), 'horizontal'),
    (dict(direction=[float('nan'), 0., 0.]), 'non-finite'),
    (dict(direction=[-1., 0.]), '3 numbers'),
    (dict(distance_m=0.0), 'declared range'),
    (dict(distance_m=0.5), 'declared range'),
    (dict(distance_m=float('inf')), 'finite'),
    (dict(overdrive_m=0.0), 'declared range'),
    (dict(overdrive_m=0.9), 'declared range'),
    (dict(contact_height_m=9.0), 'workspace'),
    (dict(max_increments=99), 'max_increments'),
])
def test_invalid_goals_are_typed_and_dispatch_nothing(change, needle):
    goal = dict(GOAL)
    goal.update(change)
    world = World(BOX_A)
    result = run(world, goal)
    assert result['outcome'] == push.OUTCOME_FAILED
    assert result['error_code'] == push.ERR_INVALID_GOAL
    assert needle in result['detail']
    assert world.moves == [] and world.reads == 0


def test_missing_contact_height_refuses_instead_of_guessing():
    """The measured reason this must fail: 0.1775 missed the box by 145 mm."""
    goal = dict(GOAL)
    goal.pop('contact_height_m')
    world = World(BOX_A)
    result = run(world, goal)
    assert result['error_code'] == push.ERR_INVALID_GOAL
    assert 'contact_height_m' in result['detail']
    assert world.moves == []


def test_contact_height_can_come_from_the_declared_parameter():
    goal = dict(GOAL)
    goal.pop('contact_height_m')
    world = World(BOX_A, script=[[-0.010, 0, 0]] * 5 + [[0, 0, 0]] * 5)
    result = run(world, goal, params={'contact_height_m': 0.031})
    assert result['resolved']['contact_height_m'] == 0.031
    # The height is used, not merely stored: the contact pose carries it.
    assert world.moves[0][2] == pytest.approx(0.031)


def test_explicit_contact_height_overrides_the_parameter():
    goal = dict(GOAL)
    goal['contact_height_m'] = 0.033
    world = World(BOX_A, script=[[-0.010, 0, 0]] * 5 + [[0, 0, 0]] * 5)
    result = run(world, goal, params={'contact_height_m': 0.050})
    assert result['resolved']['contact_height_m'] == 0.033


# ------------------------------------------------------- measured verdicts
def test_the_measured_run3_is_a_failure_not_a_success():
    """23.02 mm of 30 mm requested, with the arm still going: contact lost.

    This is the single most important assertion in the file. The archived run
    reports every end-effector move as SUCCEEDED; only the object says the push
    failed. If this test ever passes with SUCCEEDED, the skill has started
    grading the arm instead of the box.
    """
    metrics, _ = push.contact_metrics(BOX_A, MEASURED_AFTER_RUN3, GOAL['direction'])
    assert metrics['displacement_m'] == pytest.approx(MEASURED_DISPLACEMENT_RUN3, abs=1e-6)
    resolved, _ = push.resolve_goal(GOAL)
    verdict = push.judge(metrics, resolved, None, arm_travel_m=0.048,
                         reach_error_m=0.006, contact_lost_at_increment=4,
                         carry_engaged=False, increments_executed=4)
    assert verdict['outcome'] == push.OUTCOME_FAILED
    assert verdict['error_code'] == push.ERR_CONTACT_LOST
    assert verdict['contact_made'] is True and verdict['contact_lost'] is True


def test_the_same_measurement_succeeds_for_a_distance_it_actually_met():
    """Guards the other direction: 23 mm IS a success at 20 mm requested.

    Without this, a skill that always reported failure would pass the test
    above. The verdict must depend on the requested distance, not on a constant.
    """
    # 4 increments of 5 mm = exactly the 20 mm asked for, then the box stops.
    world = World(BOX_A, script=[[-0.005, 0, 0]] * 4 + [[0, 0, 0]] * 20)
    goal = dict(GOAL, distance_m=0.020)
    result = run(world, goal)
    assert result['outcome'] == push.OUTCOME_SUCCEEDED, result['detail']
    assert result['displacement_m'] == pytest.approx(0.020, abs=1e-9)


def test_run2_missing_contact_is_diagnosed_as_contact_not_made():
    """The archived false negative: the fingers passed 145 mm above the box.

    That run looks identical to a successful no-op push in every end-effector
    log. The only distinguishing evidence is that the object did not move.
    """
    world = World(BOX_A, script=[[0, 0, 0]] * 5 + [[0, 0, 0]] * 5)
    result = run(world)
    assert result['outcome'] == push.OUTCOME_FAILED
    assert result['error_code'] == push.ERR_CONTACT_NOT_MADE
    assert result['contact_made'] is False


def test_blocked_arm_is_distinguished_from_never_touching_the_object():
    """Both leave the box still; only the arm's reach error tells them apart."""
    # Approach succeeds (move 1), every increment is blocked: the arm is
    # against something it cannot get through, and the object does not move.
    world = World(BOX_A, script=[[0, 0, 0]] * 10, reach_from=1)
    result = run(world)
    assert result['outcome'] == push.OUTCOME_FAILED
    assert result['error_code'] == push.ERR_PUSH_BLOCKED
    assert result['contact_made'] is False


def test_contact_loss_is_reported_at_the_increment_where_it_happened():
    """Saturation must be localised, not inferred from a final shortfall.

    Scripted: 5 increments of 10 mm; the box follows for 2, then stops. The
    loss is at increment 3, and the skill must say so (the operator needs to
    know where contact ended, not just that the total was short).
    """
    script = [[-0.010, 0, 0], [-0.010, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0],
              [0, 0, 0]]
    world = World(BOX_A, script=script)
    result = run(world, dict(GOAL, distance_m=0.040, overdrive_m=0.01))
    assert result['outcome'] == push.OUTCOME_FAILED
    assert result['error_code'] == push.ERR_CONTACT_LOST
    assert result['contact_lost_at_increment'] == 3
    # It stopped as soon as contact was lost rather than grinding on.
    assert result['increments_executed'] == 3


def test_off_axis_displacement_is_refused():
    """A push that sends the box sideways is not the requested push."""
    metrics, _ = push.contact_metrics(BOX_A, [0.220, 0.200, 0.0175], [-1., 0., 0.])
    resolved, _ = push.resolve_goal(GOAL)
    verdict = push.judge(metrics, resolved, None, arm_travel_m=0.05,
                         reach_error_m=0.005, contact_lost_at_increment=0,
                         carry_engaged=False, increments_executed=5)
    assert verdict['error_code'] == push.ERR_DISPLACEMENT_OFF_AXIS


def test_lifted_or_tipped_object_is_refused():
    metrics, _ = push.contact_metrics(BOX_A, [-0.030 + 0.220, 0.0, 0.2175], [-1., 0., 0.])
    resolved, _ = push.resolve_goal(GOAL)
    verdict = push.judge(metrics, resolved, None, arm_travel_m=0.05,
                         reach_error_m=0.005, contact_lost_at_increment=0,
                         carry_engaged=False, increments_executed=5)
    assert verdict['error_code'] == push.ERR_DISPLACEMENT_OFF_AXIS
    assert 'lifted or tipped' in verdict['detail']


def test_a_carried_object_never_counts_as_a_push():
    """The anti-fake-success rule: if carry engaged, the evidence is void."""
    metrics, _ = push.contact_metrics(BOX_A, MEASURED_AFTER_RUN3, GOAL['direction'])
    resolved, _ = push.resolve_goal(GOAL, {'push_min_distance_m': 0.01})
    verdict = push.judge(metrics, resolved, {'push_min_distance_m': 0.01},
                         arm_travel_m=0.05, reach_error_m=0.005,
                         contact_lost_at_increment=0, carry_engaged=True,
                         increments_executed=5)
    assert verdict['outcome'] == push.OUTCOME_FAILED
    assert verdict['error_code'] == push.ERR_PUSH_BLOCKED
    assert 'carry backend engaged' in verdict['detail']


def test_carry_engaging_mid_push_aborts_immediately():
    world = World(BOX_A, script=[[-0.010, 0, 0]] * 6, carry_engaged_at=2)
    result = run(world)
    assert result['error_code'] == push.ERR_PUSH_BLOCKED
    assert result['carry_engaged_during'] is True


# ------------------------------------------------------------- execution
def test_approach_retreat_and_increment_shape():
    # 5 increments of 10 mm EE travel; the box follows for exactly 3 of them
    # (30 mm = the requested distance) and then stays put.
    world = World(BOX_A, script=[[-0.010, 0, 0]] * 3 + [[0, 0, 0]] * 8)
    result = run(world, dict(GOAL, max_increments=5))
    assert result['outcome'] == push.OUTCOME_SUCCEEDED, result['detail']
    # approach + 5 increments + retreat
    assert len(world.moves) == 7
    # Near face along the push direction: centre - direction*half. The push
    # direction is -x, so the contacted face is the +x face of the box.
    face_x = BOX_A[0] - (-1.0) * 0.0175
    # The approach stands off BEFORE the face; every increment moves along -x;
    # the last increment is overdrive past the requested distance.
    assert world.moves[0][0] > face_x
    xs = [move[0] for move in world.moves[1:6]]
    assert xs == sorted(xs, reverse=True)
    assert face_x - xs[-1] == pytest.approx(0.030 + 0.020, abs=1e-9)
    assert world.phases == ['VALIDATING', 'OBSERVING', 'APPROACH', 'PUSHING',
                            'VERIFYING', 'RETREATING']


def test_cancel_before_motion_dispatches_nothing():
    world = World(BOX_A)
    world.cancelled_flag = True
    result = run(world)
    assert result['outcome'] == push.OUTCOME_CANCELED
    assert world.moves == []


def test_cancel_mid_push_keeps_the_measured_displacement():
    world = World(BOX_A, script=[[-0.005, 0, 0]] * 10)
    world_probe = world

    original = world.move_to

    def cancel_after_two(target):
        result = original(target)
        if len(world.moves) >= 3:       # approach + 2 increments
            world_probe.cancelled_flag = True
        return result

    world.move_to = cancel_after_two
    result = run(world)
    assert result['outcome'] == push.OUTCOME_CANCELED
    assert result['error_code'] == push.ERR_CANCELED
    # The partial measurement is kept: a cancelled push still measured
    # something, and discarding it would hide real object motion.
    assert result['displacement_m'] > 0


def test_runaway_push_is_not_accepted_as_a_success():
    """A single huge shove must not satisfy the request.

    The contract's own displacement tolerance refuses it before the axis checks,
    which is why this asserts on the code rather than the wording.
    """
    world = World(BOX_A, script=[[-0.030, 0, 0]] * 5 + [[0, 0, 0]] * 5)
    result = run(world)
    assert result['outcome'] == push.OUTCOME_FAILED
    assert result['displacement_m'] > GOAL['distance_m']


def test_metrics_never_report_zero_direction_for_a_still_object():
    """Cosine of a zero displacement is undefined, so it must be NaN."""
    metrics, _ = push.contact_metrics(BOX_A, list(BOX_A), [-1., 0., 0.])
    assert metrics['displacement_m'] == 0.0
    assert math.isnan(metrics['direction_cos'])
