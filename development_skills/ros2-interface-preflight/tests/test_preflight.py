"""Tests for the ROS 2 interface preflight.

Design note: these tests do NOT need ROS. validate_stage and validate_goal are duck typed,
so the negative cases can be built from plain objects. A checker that could only be tested
inside a ROS environment would rarely be tested at all.

Every negative case below corresponds to a real failure from this session, so a test turning
green means the failure mode is covered rather than assumed covered.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import preflight  # noqa: E402


class P:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def stage(frame="world", quat=(0.0, 0.0, 0.0, 1.0), name="probe", sid="s-0"):
    pose = P(header=P(frame_id=frame),
             pose=P(orientation=P(x=quat[0], y=quat[1], z=quat[2], w=quat[3])))
    return P(stage_id=sid, object_name=name, place_pose=pose)


def goal(stages=None, objects=None, tol=0.02, clearance=0.05):
    if stages is None:
        stages = [stage()]
    if objects is None:
        objects = [P(object_name="probe")]
    return P(stages=stages, initial_objects=objects,
             position_tolerance_m=tol, clearance_m=clearance)


# ---------------------------------------------------------------- positive

def test_a_correct_stage_has_no_problems():
    assert preflight.validate_stage(stage()) == []


def test_a_correct_goal_has_no_problems():
    assert preflight.validate_goal(goal()) == []


# ------------------------------------------- the real failure modes

def test_case_6_missing_world_frame_is_rejected():
    """Real failure: header.frame_id left empty -> executor ValueError."""
    problems = preflight.validate_stage(stage(frame=""))
    assert any("frame_id" in p for p in problems), problems


def test_case_6b_non_identity_quaternion_is_rejected():
    """The executor compares [x,y,z,w] to [0,0,0,1] as an exact list.

    0.99999 is not 1.0, so an approximate quaternion must be rejected.
    """
    problems = preflight.validate_stage(stage(quat=(0.0, 0.0, 0.0, 0.99999)))
    assert any("orientation" in p for p in problems), problems


def test_case_4_initial_object_without_object_name_is_rejected():
    """Real failure: used .name, the field is .object_name."""
    objects = [P(name="probe")]
    problems = preflight.validate_goal(goal(objects=objects))
    assert any("object_name" in p for p in problems), problems


def test_case_4b_empty_initial_objects_is_rejected():
    """Real failure: empty list -> executor CompositeError 60."""
    problems = preflight.validate_goal(goal(objects=[]))
    assert any("initial_objects" in p for p in problems), problems


def test_stage_count_bounds_are_enforced():
    """Real failure: zero stages reached the executor."""
    problems = preflight.validate_goal(goal(stages=[]))
    assert any("stages" in p for p in problems), problems
    too_many = [stage(sid="s-%d" % i) for i in range(9)]
    problems = preflight.validate_goal(goal(stages=too_many))
    assert any("stages" in p for p in problems), problems


def test_tolerance_bounds_are_enforced():
    assert preflight.validate_goal(goal(tol=0.0)) != []
    assert preflight.validate_goal(goal(tol=0.061)) != []


def test_clearance_bounds_are_enforced():
    assert preflight.validate_goal(goal(clearance=0.04)) != []
    assert preflight.validate_goal(goal(clearance=0.26)) != []


def test_a_non_numeric_tolerance_is_rejected():
    assert preflight.validate_goal(goal(tol="0.02")) != []


# -------------------------------------------------------------- mutation

def test_the_frame_rule_is_not_vacuous():
    """If REQUIRED_FRAME were anything but world, the empty-frame case would pass.

    This asserts the constant is load-bearing rather than decorative.
    """
    assert preflight.REQUIRED_FRAME == "world"
    assert preflight.validate_stage(stage(frame="world")) == []
    assert preflight.validate_stage(stage(frame="base_link")) != []
