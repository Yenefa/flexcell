"""Post-return feedback must not turn positive stroke sums into success."""
import pytest

from flexcell_skills.contracts.push_recover import arm_quiet, measured_next_request

START = [.22, 0., .0175]
GOAL = dict(direction=[-1., 0.], min_displacement_m=.03,
            max_displacement_m=.15, max_vertical_m=.02, min_direction_cosine=.9)
ZONE = dict(pose=[.12, 0., .0175], radius=.06)


def choose(current, remaining=3, **kwargs):
    return measured_next_request(START, current, GOAL, ZONE, remaining, **kwargs)


def test_archived_reverse_motion_is_negative_not_positive_stroke_sum():
    action, state = choose([.2794440731, 0., .0175])
    assert action == 'push'
    assert state['net_along_m'] == pytest.approx(-.0594440731)
    assert state['distance_m'] == .03


def test_stop_when_known_zone_goal_is_met_before_nominal_ninety_mm():
    action, state = choose([.17, 0., .0175])
    assert action == 'goal_geometry_reached'
    assert state['net_along_m'] == pytest.approx(.05)
    assert 'distance_m' not in state


def test_passing_geometry_does_not_need_another_push_when_budget_is_empty():
    assert choose([.17, 0., .0175], remaining=0)[0] == 'goal_geometry_reached'


def test_no_budget_cannot_dispatch_a_shortfall():
    assert choose([.21, 0., .0175], remaining=0)[0] == 'exhausted'


def test_large_old_stroke_report_cannot_replace_current_pose():
    action, state = choose([.215, 0., .0175])
    assert action == 'push'
    assert state['net_along_m'] == pytest.approx(.005)
    assert state['distance_m'] == .03


@pytest.mark.parametrize('point', [[.04, 0., .0175], [.17, 0., .06]])
def test_envelope_violation_stops(point):
    assert choose(point)[0] == 'blocked'


def test_protected_motion_blocks_even_a_reached_red_goal():
    assert choose([.17, 0., .0175], protected_motion_m=.006)[0] == 'blocked'


def test_wrong_axis_near_nominal_goal_does_not_invent_a_minimum_extra_push():
    assert choose([.135, .075, .0175])[0] == 'blocked'


@pytest.mark.parametrize('bad', [[float('nan'), 0., .0175], [True, 0., .0175]])
def test_unknown_pose_is_not_zero_progress(bad):
    with pytest.raises(ValueError):
        choose(bad)


def test_direction_comes_from_the_goal_not_a_hardcoded_negative_x():
    goal = dict(GOAL, direction=[0., 1.])
    action, state = measured_next_request([0., 0., .0175], [0., .05, .0175],
        goal, dict(pose=[0., .1, .0175], radius=.06), 3)
    assert action == 'goal_geometry_reached'
    assert state['net_along_m'] == pytest.approx(.05)


def test_nonfinite_zone_does_not_dispatch():
    with pytest.raises(ValueError):
        measured_next_request(START, START, GOAL, dict(ZONE, radius=float('nan')), 3)


@pytest.mark.parametrize('velocities,age', [([0., 0., 0.], 0.),
    ([0., 0., float('nan'), 0.], 0.), ([0., .1, 0., 0.], 0.),
    ([0., 0., 0., 0.], 1.)])
def test_unknown_or_moving_joint_state_is_not_quiet(velocities, age):
    assert not arm_quiet(['joint1', 'joint2', 'joint3', 'joint4'], velocities, age)


def test_fresh_measured_zero_velocity_is_quiet():
    assert arm_quiet(['joint1', 'joint2', 'joint3', 'joint4'], [0., 0., 0., 0.], .02)
