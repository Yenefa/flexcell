"""Shared WorldState msg fixture for executor-level tests (keeps every
suite's canonical-envelope fixtures byte-consistent)."""

from geometry_msgs.msg import Pose
from std_msgs.msg import Header as StdHeader

from flexcell_interfaces.msg import (
    CarryState, RobotStateSummary, WorldObject, WorldState, ZoneState)


def _pose(x=0.0, y=0.0, z=0.0175):
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z
    p.orientation.w = 1.0
    return p


def world_state_msg(revision=7):
    """A fully-populated v2 WorldState (mirrors observe_server's snapshot)."""
    ws = WorldState()
    ws.header = StdHeader()
    ws.header.frame_id = 'world'
    ws.revision = revision
    ws.source = 'SIMULATION_GROUND_TRUTH'
    ws.schema_version = '2.0'
    ws.robot = RobotStateSummary()
    ws.robot.ee_frame = 'end_effector_link'
    ws.robot.joint_names = ['joint1', 'joint2', 'joint3', 'joint4']
    ws.robot.positions = [0.6048, -0.8972, 0.895, 0.4939]
    ws.robot.ee_pose = _pose(0.22, 0.0, 0.177)
    ws.robot.gripper_joint_name = 'gripper_joint_1'
    ws.robot.gripper_position = 0.011
    ws.robot.has_gripper_state = True
    a = WorldObject()
    a.name, a.klass, a.available = 'target_box_a', 'box', True
    a.pose, a.size = _pose(0.22, 0.0), [0.035, 0.035, 0.035]
    a.pose_age_s = 0.042
    ws.objects.append(a)
    b = WorldObject()
    b.name, b.klass, b.available = 'target_box_b', 'box', True
    b.pose, b.size = _pose(0.20, -0.18), [0.035, 0.035, 0.035]
    b.pose_age_s = 0.042
    ws.objects.append(b)
    ws.carry = CarryState()
    ws.carry.engaged = False
    z = ZoneState()
    z.id, z.occupancy = 'zone_1', 0
    from geometry_msgs.msg import Point
    pt = Point()
    pt.x, pt.y, pt.z = 0.12, -0.15, 0.0175
    z.center = pt
    ws.zones.append(z)
    return ws
