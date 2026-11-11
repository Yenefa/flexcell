"""Verify a RunComposite goal can be constructed WITHOUT starting Gazebo.

Four times in one session a driver failed at runtime because a message field name or
type was guessed instead of read: "success" for a Result field, "direction_cosine" vs
"direction_cos", a node where sample_gz_pose wanted a model name, "name" where
ObjectPosition declares "object_name", and a Point where CompositeStage declares a
PoseStamped. Each one cost a full simulator start and teardown to discover.

None of those needed Gazebo. They are static interface facts. This script asserts the
interface before any simulation is launched, so the whole class of error is caught in a
second instead of in five minutes.

It also PRINTS the declared field names, so the next driver is written from the real
definition rather than from memory.
"""
import sys

FAILED = []


def check(label, fn):
    try:
        fn()
        print("  ok   %s" % label)
    except Exception as exc:
        FAILED.append("%s: %s" % (label, exc))
        print("  FAIL %s -> %s" % (label, exc))


print("=== imports ===")
try:
    from flexcell_interfaces.action import RunComposite, PushObject
    from flexcell_interfaces.msg import CompositeStage, ObjectPosition
    from geometry_msgs.msg import Point, PoseStamped
    print("  ok   imports")
except Exception as exc:
    print("  FAIL imports -> %s" % exc)
    raise SystemExit(1)

print("=== declared field names ===")
print("  RunComposite.Goal   :", sorted(RunComposite.Goal.get_fields_and_field_types()))
print("  RunComposite.Result :", sorted(RunComposite.Result.get_fields_and_field_types()))
print("  CompositeStage      :", sorted(CompositeStage.get_fields_and_field_types()))
print("  ObjectPosition      :", sorted(ObjectPosition.get_fields_and_field_types()))

print("=== construct exactly as the drivers do ===")


def build_stage():
    s = CompositeStage()
    s.stage_id = "target_box_a-0"
    s.object_name = "target_box_a"
    ps = PoseStamped()
    ps.header.frame_id = "world"
    ps.pose.position = Point(x=0.1, y=0.1, z=0.0)
    ps.pose.orientation.w = 1.0
    s.place_pose = ps
    assert s.place_pose.pose.position.x == 0.1
    # task_fsm_server rejects anything else, and the check is an exact list compare.
    q = s.place_pose.pose.orientation
    assert s.place_pose.header.frame_id == "world", s.place_pose.header.frame_id
    assert [q.x, q.y, q.z, q.w] == [0.0, 0.0, 0.0, 1.0], [q.x, q.y, q.z, q.w]


def build_initial_objects():
    op = ObjectPosition()
    op.object_name = "target_box_a"
    op.position = Point(x=0.22, y=0.0, z=0.0175)
    assert op.object_name == "target_box_a"
    return [op]


def build_goal():
    g = RunComposite.Goal()
    g.scenario_id = "T01-train-seed1000"
    g.motion_profile_id = "legacy"
    g.position_tolerance_m = 0.02
    g.clearance_m = 0.05
    g.pause_after_stages = 0
    g.resume_run_id = ""
    g.resume_receipt_sha256 = ""
    g.initial_objects = build_initial_objects()
    build_stage()
    s = CompositeStage()
    s.stage_id = "x-0"
    s.object_name = "target_box_a"
    ps = PoseStamped()
    ps.pose.position = Point(x=0.0, y=0.0, z=0.0)
    ps.pose.orientation.w = 1.0
    s.place_pose = ps
    g.stages = [s]
    assert len(g.stages) == 1


def check_push_result_fields():
    names = PushObject.Result.get_fields_and_field_types()
    assert "direction_cos" in names, names
    assert "displacement_m" in names, names
    assert "success" not in names, names


check("CompositeStage + world-framed identity PoseStamped", build_stage)
check("ObjectPosition.object_name", build_initial_objects)
check("RunComposite.Goal full construction", build_goal)
check("PushObject.Result field names", check_push_result_fields)

print()
if FAILED:
    print("INTERFACE_CHECK_FAILED (%d)" % len(FAILED))
    for f in FAILED:
        print("  -", f)
    raise SystemExit(1)
print("INTERFACE_CHECK_OK -- safe to launch the simulator")