#!/usr/bin/env python3
"""Unit tests for the WorldState v2 canonical contract (issue #3).

Run inside the ROS environment (needs flexcell_interfaces built + sourced):

    python3 test/test_canonical_state.py

Covers: construct / serialize / deserialize / validate required fields, plus
determinism, the schema-version gate and the notes[] exclusion rule (ADR-002).
"""

import unittest

from geometry_msgs.msg import Point, Pose
from std_msgs.msg import Header as StdHeader

from flexcell_interfaces.msg import (
    Assignment, CarryState, HistoryEntry, RobotStateSummary, TaskConstraints,
    TaskContext, WorldObject, WorldState, ZoneState)

from flexcell_skills.canonical_state import (
    SCHEMA_VERSION, SCHEMA_VERSION_KEY, UnsupportedSchemaVersionError,
    build_envelope, deserialize_envelope, serialize_dict, serialize_envelope,
    validate_envelope, validate_or_raise)


def _pose(x=0.0, y=0.0, z=0.0175):
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z
    p.orientation.w = 1.0
    return p


def _world_state(dirty_x=None):
    """A fully-populated v2 WorldState (mirrors observe_server's snapshot)."""
    ws = WorldState()
    ws.header = StdHeader()
    ws.header.stamp.sec = 1790431668
    ws.header.stamp.nanosec = 430272000
    ws.header.frame_id = 'world'
    ws.revision = 7
    ws.source = 'SIMULATION_GROUND_TRUTH'
    ws.schema_version = '2.0'

    ws.robot.ee_frame = 'end_effector_link'
    ws.robot.joint_names = ['joint1', 'joint2', 'joint3', 'joint4']
    ws.robot.positions = [0.6048, -0.8972, 0.895, 0.4939]
    ws.robot.ee_pose = _pose(0.22, 0.0, 0.177)
    ws.robot.gripper_joint_name = 'gripper_joint_1'
    ws.robot.gripper_position = 0.011
    ws.robot.has_gripper_state = True

    x = 0.22 if dirty_x is None else dirty_x
    a = WorldObject()
    a.name, a.klass, a.available = 'target_box_a', 'box', True
    a.pose, a.size = _pose(x, 0.0), [0.035, 0.035, 0.035]
    a.pose_age_s = 0.042
    b = WorldObject()
    b.name, b.klass, b.available = 'target_box_b', 'box', True
    b.pose, b.size = _pose(0.20, -0.18), [0.035, 0.035, 0.035]
    b.pose_age_s = 0.039
    ws.objects = [a, b]

    ws.carry.engaged = False
    ws.carry.object_id = ''
    ws.carry.reference_frame = 'world'
    ws.carry.offset = [0.0, 0.0, 0.0]

    z1 = ZoneState()
    z1.id, z1.radius, z1.occupancy, z1.occupied_by = 'zone_1', 0.06, 1, 'target_box_a'
    z1.center = Point()
    z1.center.x, z1.center.y, z1.center.z = 0.12, -0.15, 0.0175
    z2 = ZoneState()
    z2.id, z2.radius, z2.occupancy, z2.occupied_by = 'zone_2', 0.06, 0, ''
    z2.center = Point()
    z2.center.x, z2.center.y, z2.center.z = 0.25, 0.05, 0.0175
    ws.zones = [z1, z2]

    ws.notes = ['diagnostics only - must never reach a policy']
    return ws


def _task_context():
    tc = TaskContext()
    tc.task_state = 'RUNNING'
    tc.goal_id = 'goal-week1-demo-0001'
    tc.scenario_id = 'week1_demo_v1'
    remaining = Assignment()
    remaining.object_id, remaining.zone_id = 'target_box_b', 'zone_2'
    remaining.outcome, remaining.error_code = Assignment.OUTCOME_NONE, 0
    tc.plan_remaining = [remaining]
    done = Assignment()
    done.object_id, done.zone_id = 'target_box_a', 'zone_1'
    done.outcome, done.error_code = 0, 0
    tc.plan_completed = [done]
    tc.retry_counts = [0]
    tc.recovery_budget_remaining = 1
    tc.last_action = 'PLACE'
    tc.last_outcome = 0
    tc.last_error_code = 0
    tc.last_action_world_revision = 6
    tc.available_actions = ['OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'WAIT', 'ABORT']
    tc.deadline_remaining_s = 118.4
    tc.fault_injection_active = False

    tc.constraints.allowed_actions = ['OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'WAIT', 'ABORT']
    tc.constraints.recovery_budget = 1
    tc.constraints.verify_tolerance_m = 0.06
    tc.constraints.motion_profile_id = 'demo_slow'
    tc.constraints.max_world_age_s = 1.5

    entry = HistoryEntry()
    entry.seq, entry.action, entry.target = 1, 'PLACE', 'target_box_a/zone_1'
    entry.outcome, entry.error_code, entry.attempt = 0, 0, 1
    entry.world_revision, entry.evidence_id = 6, 'auto-3-64332a7c-8ee3ceb7'
    tc.history = [entry]
    return tc


class TestConstruct(unittest.TestCase):

    def test_construct_v2_world_state(self):
        ws = _world_state()
        tc = _task_context()
        self.assertEqual(ws.schema_version, '2.0')
        self.assertEqual(ws.revision, 7)
        self.assertEqual([o.klass for o in ws.objects], ['box', 'box'])
        self.assertTrue(ws.robot.has_gripper_state)
        self.assertEqual(ws.robot.gripper_joint_name, 'gripper_joint_1')
        self.assertEqual([z.occupied_by for z in ws.zones],
                         ['target_box_a', ''])
        self.assertEqual(tc.constraints.recovery_budget, 1)
        self.assertEqual(len(tc.history), 1)
        self.assertEqual(tc.history[0].evidence_id, 'auto-3-64332a7c-8ee3ceb7')

    def test_build_envelope_uses_ws_task_by_default(self):
        ws = _world_state()
        ws.task = _task_context()
        env = build_envelope(ws)
        self.assertEqual(env[SCHEMA_VERSION_KEY], SCHEMA_VERSION)
        self.assertEqual(env['task_context']['goal_id'], 'goal-week1-demo-0001')


class TestSerialize(unittest.TestCase):

    def test_serialize_deterministic(self):
        ws, tc = _world_state(), _task_context()
        self.assertEqual(serialize_envelope(ws, tc), serialize_envelope(ws, tc))

    def test_serialize_key_order_independent(self):
        ws, tc = _world_state(), _task_context()
        env = build_envelope(ws, tc)
        shuffled = {k: env[k] for k in reversed(list(env.keys()))}
        self.assertEqual(serialize_dict(env), serialize_dict(shuffled))

    def test_serialize_float_determinism(self):
        a = serialize_envelope(_world_state(dirty_x=0.1 + 0.2), _task_context())
        b = serialize_envelope(_world_state(dirty_x=0.3), _task_context())
        self.assertEqual(a, b)  # 9-decimal rounding absorbs float noise

    def test_notes_never_serialized(self):
        text = serialize_envelope(_world_state(), _task_context())
        self.assertNotIn('notes', text)
        self.assertNotIn('diagnostics only', text)


class TestDeserialize(unittest.TestCase):

    def test_roundtrip_is_byte_stable(self):
        ws, tc = _world_state(), _task_context()
        text = serialize_envelope(ws, tc)
        env = deserialize_envelope(text)
        self.assertEqual(serialize_dict(env), text)
        self.assertEqual(env['world_state']['revision'], 7)
        self.assertEqual(env['world_state']['objects'][0]['klass'], 'box')
        self.assertEqual(env['task_context']['constraints']['recovery_budget'], 1)
        self.assertEqual(env['task_context']['history'][0]['seq'], 1)

    def test_version_gate_rejects_unknown(self):
        ws, tc = _world_state(), _task_context()
        env = build_envelope(ws, tc)
        env[SCHEMA_VERSION_KEY] = 999
        with self.assertRaises(UnsupportedSchemaVersionError):
            deserialize_envelope(serialize_dict(env))
        del env[SCHEMA_VERSION_KEY]
        with self.assertRaises(UnsupportedSchemaVersionError):
            deserialize_envelope(serialize_dict(env))

    def test_version_gate_accepts_current(self):
        env = deserialize_envelope(serialize_envelope(_world_state(), _task_context()))
        self.assertEqual(env[SCHEMA_VERSION_KEY], 2)


class TestValidate(unittest.TestCase):

    def test_valid_envelope_has_no_violations(self):
        env = build_envelope(_world_state(), _task_context())
        self.assertEqual(validate_envelope(env), [])
        validate_or_raise(env)

    def test_missing_required_fields_listed(self):
        env = build_envelope(_world_state(), _task_context())
        del env['world_state']['revision']
        del env['world_state']['source']
        del env['world_state']['objects'][0]['name']
        del env['world_state']['zones'][1]['id']
        del env['task_context']['constraints']
        del env['task_context']['history'][0]['seq']
        violations = validate_envelope(env)
        joined = '; '.join(violations)
        for path in ('world_state.revision', 'world_state.source',
                     'world_state.objects[0].name', 'world_state.zones[1].id',
                     'task_context.constraints', 'task_context.history[0].seq'):
            self.assertIn(path, joined)

    def test_bad_occupancy_rejected(self):
        env = build_envelope(_world_state(), _task_context())
        env['world_state']['zones'][0]['occupancy'] = 7
        self.assertTrue(any('occupancy' in v for v in validate_envelope(env)))

    def test_wrong_version_is_a_violation(self):
        env = build_envelope(_world_state(), _task_context())
        env[SCHEMA_VERSION_KEY] = 1
        self.assertTrue(any(SCHEMA_VERSION_KEY in v for v in validate_envelope(env)))


if __name__ == '__main__':
    unittest.main()
