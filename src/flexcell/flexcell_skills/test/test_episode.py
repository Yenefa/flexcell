#!/usr/bin/env python3
"""Unit tests for the episode record + policy-input replay contract
(issue #7 / §4.4).  Runs inside the ROS environment like the other suites;
the episode contract itself is pure python.

Covers: record/replay round-trip for happy + recovery paths (S1/S2 shape),
multi-leg episodes, canonical-envelope round trip, byte determinism, schema
version keys, NaN sanitization, divergence detection.
"""

import unittest

from std_msgs.msg import Header as StdHeader
from geometry_msgs.msg import Point, Pose

from flexcell_interfaces.msg import (
    CarryState, RobotStateSummary, WorldObject, WorldState, ZoneState)

from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.contracts.episode import (
    EPISODE_SCHEMA_VERSION, EPISODE_SCHEMA_VERSION_KEY, EpisodeRecorder,
    env_snapshot, replay_episode, serialize_episode)
from flexcell_skills.decision_policy import (
    ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY, Constraints,
    FSMPolicy, HistoryRecord, TaskGoal)


def _pose(x=0.0, y=0.0, z=0.0175):
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z
    p.orientation.w = 1.0
    return p


def _world_state(revision=7):
    """A populated v2 WorldState (mirrors observe_server's snapshot)."""
    ws = WorldState()
    ws.header = StdHeader()
    ws.header.stamp.sec = 1790431668
    ws.header.stamp.nanosec = 430272000
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
    ws.carry = CarryState()
    ws.carry.engaged = False
    z = ZoneState()
    z.id, z.occupancy = 'zone_1', 0
    c = Point()
    c.x, c.y, c.z = 0.12, -0.15, 0.0175
    z.center = c
    ws.zones.append(z)
    return ws


def _goal(*assignments):
    return TaskGoal('goal-1', 'week1_demo_v1',
                    tuple(assignments))


def _constraints(budget=1):
    return Constraints(
        frozenset((ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
                   'WAIT', 'ABORT')),
        budget, 0.06, 'demo_slow', 0.0)


def _drive(policy, recorder, goal, constraints, outcomes, world_text):
    """Drive the executor loop against the live policy, recording every
    decision through the recorder - the same shape task_fsm uses."""
    history = []
    verified = 0
    while verified < len(goal.assignments):
        recorder.begin_step(world_text, goal, constraints, history)
        decision = policy.decide(None, goal, constraints, tuple(history))
        recorder.record_decision(decision, 0)
        oc, ec = outcomes[decision.action].pop(0)
        recorder.record_executor_result(outcome=oc, error_code=ec,
                                        evidence_id='ev-%d' % len(history))
        history.append(HistoryRecord(
            decision.action, decision.target, oc, ec,
            2 if (decision.action == ACTION_PICK and
                  any(h.action == ACTION_PICK for h in history)) else 1,
            0, 'ev-%d' % len(history)))
        if decision.action == ACTION_VERIFY and oc == 0:
            verified += 1


class TestEpisodeRecordReplay(unittest.TestCase):

    def test_happy_single_leg_round_trip(self):
        policy = FSMPolicy()
        rec = EpisodeRecorder('week1_demo_v1', 'run-happy', policy.name,
                              policy.version)
        ok = (0, 0)
        _drive(policy, rec, _goal(('target_box_a', 'zone_1')),
               _constraints(), {a: [ok] for a in
                                (ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE,
                                 ACTION_VERIFY)},
               world_text=None)
        record = rec.to_dict(final_state={'outcome': 'SUCCEEDED'})
        self.assertEqual(record[EPISODE_SCHEMA_VERSION_KEY],
                         EPISODE_SCHEMA_VERSION)
        results = replay_episode(record, FSMPolicy())
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertTrue(r['ok'], r['detail'])

    def test_recovery_path_round_trip(self):
        policy = FSMPolicy()
        rec = EpisodeRecorder('recovery_demo_v1', 'run-recovery', policy.name,
                              policy.version)
        record = self._recovery_episode(rec, policy)
        results = replay_episode(record, FSMPolicy())
        self.assertEqual(len(results), 6)
        for r in results:
            self.assertTrue(r['ok'], r['detail'])
        # the recorded trace must show the recovery shape
        actions = [s['policy_output']['action'] for s in record['steps']]
        self.assertEqual(
            actions,
            [ACTION_OBSERVE, ACTION_PICK, ACTION_OBSERVE, ACTION_PICK,
             ACTION_PLACE, ACTION_VERIFY])

    def _recovery_episode(self, rec, policy):
        ok = (0, 0)
        outcomes = {
            ACTION_OBSERVE: [ok, ok],
            ACTION_PICK: [(1, 23), ok],   # first attempt fails GRASP_FAILED
            ACTION_PLACE: [ok],
            ACTION_VERIFY: [ok],
        }
        _drive(policy, rec, _goal(('target_box_a', 'zone_1')),
               _constraints(), outcomes, world_text=None)
        return rec.to_dict(final_state={'outcome': 'SUCCEEDED'})

    def test_two_leg_episode_round_trip(self):
        policy = FSMPolicy()
        rec = EpisodeRecorder('week1_demo_v1', 'run-twoleg', policy.name,
                              policy.version)
        ok = (0, 0)
        _drive(policy, rec,
               _goal(('target_box_a', 'zone_1'), ('target_box_b', 'zone_2')),
               _constraints(), {a: [ok] * 4 for a in
                                (ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE,
                                 ACTION_VERIFY)},
               world_text=None)
        record = rec.to_dict()
        results = replay_episode(record, FSMPolicy())
        self.assertEqual(len(results), 8)
        for r in results:
            self.assertTrue(r['ok'], r['detail'])

    def test_envelope_world_round_trip(self):
        """A recorded canonical envelope deserializes cleanly at replay."""
        policy = FSMPolicy()
        rec = EpisodeRecorder('week1_demo_v1', 'run-env', policy.name,
                              policy.version)
        ok = (0, 0)
        _drive(policy, rec, _goal(('target_box_a', 'zone_1')),
               _constraints(), {a: [ok] for a in
                                (ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE,
                                 ACTION_VERIFY)},
               world_text=serialize_envelope(_world_state()))
        record = rec.to_dict()
        self.assertIsNotNone(record['initial_world_state'])
        for r in replay_episode(record, FSMPolicy()):
            self.assertTrue(r['ok'], r['detail'])

    def test_serialization_is_deterministic_and_versioned(self):
        rec = EpisodeRecorder('week1_demo_v1', 'run-det', 'fsm', '1.0')
        ok = (0, 0)
        policy = FSMPolicy()
        _drive(policy, rec, _goal(('target_box_a', 'zone_1')),
               _constraints(), {a: [ok] for a in
                                (ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE,
                                 ACTION_VERIFY)},
               world_text=None)
        r1 = serialize_episode(rec.to_dict())
        r2 = serialize_episode(rec.to_dict())
        self.assertEqual(r1, r2)
        self.assertIn('"EpisodeSchemaVersion":1', r1)
        self.assertIn('"world_state_schema_version":2', r1)

    def test_nan_final_state_sanitized(self):
        rec = EpisodeRecorder('week1_demo_v1', 'run-nan', 'fsm', '1.0')
        record = rec.to_dict(
            final_state={'zone_a_error_m': float('nan'),
                         'zone_b_error_m': 0.0125})
        text = serialize_episode(record)   # must not raise on NaN
        self.assertIn('"zone_a_error_m":null', text)
        self.assertIn('"zone_b_error_m":0.0125', text)

    def test_divergence_detected_on_tampered_output(self):
        policy = FSMPolicy()
        rec = EpisodeRecorder('week1_demo_v1', 'run-tamper', policy.name,
                              policy.version)
        ok = (0, 0)
        _drive(policy, rec, _goal(('target_box_a', 'zone_1')),
               _constraints(), {a: [ok] for a in
                                (ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE,
                                 ACTION_VERIFY)},
               world_text=None)
        record = rec.to_dict()
        record['steps'][1]['policy_output']['action'] = 'PLACE'
        results = replay_episode(record, FSMPolicy())
        self.assertFalse(results[1]['ok'])
        self.assertTrue(results[0]['ok'])

    def test_env_snapshot_is_dict(self):
        self.assertIsInstance(env_snapshot(), dict)


if __name__ == '__main__':
    unittest.main()
