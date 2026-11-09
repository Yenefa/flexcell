"""P1-A: world freshness is real, grows with time, and can reject a decision."""
import time
import unittest

from flexcell_skills.canonical_state import serialize_envelope, world_state_to_dict
from flexcell_skills.contracts.safety_gate import STALE_WORLD, validate
from flexcell_skills.decision_policy import Constraints, Decision, TaskGoal
from geometry_msgs.msg import Pose
from flexcell_interfaces.msg import (
    WorldObject, WorldState, RobotStateSummary, CarryState, ZoneState,
    TaskContext)


def _world(age_s=0.0, sample_age_s=None):
    """Return (world, seconds_since_the_snapshot_was_received)."""
    ws = WorldState()
    ws.revision = 3
    ws.source = "SIMULATION_GROUND_TRUTH"
    ws.schema_version = "2.0"
    ws.robot = RobotStateSummary()
    ws.carry = CarryState()
    ws.task = TaskContext()
    obj = WorldObject()
    obj.name = "target_box_a"
    obj.klass = "box"
    obj.available = True
    obj.pose = Pose()
    obj.pose.orientation.w = 1.0
    obj.size = [0.035, 0.035, 0.035]
    obj.pose_age_s = age_s
    ws.objects = [obj]
    zone = ZoneState()
    zone.id = "zone_1"
    zone.center = Pose().position
    zone.radius = 0.06
    zone.occupancy = 0
    ws.zones = [zone]
    return ws, sample_age_s


class TestPoseAgeGrows(unittest.TestCase):

    def test_recorded_sample_time_replaces_the_frozen_age(self):
        ws, elapsed = _world(age_s=0.0, sample_age_s=3.5)
        doc = world_state_to_dict(ws, sampled_monotonic=time.monotonic() - elapsed)
        age = doc["objects"][0]["pose_age_s"]
        self.assertGreaterEqual(age, 3.4)
        self.assertLess(age, 4.5)

    def test_age_grows_between_two_serializations(self):
        ws, _ = _world(age_s=0.0, sample_age_s=0.0)
        received = time.monotonic()
        first = world_state_to_dict(ws, sampled_monotonic=received)["objects"][0]["pose_age_s"]
        time.sleep(0.2)
        second = world_state_to_dict(ws, sampled_monotonic=received)["objects"][0]["pose_age_s"]
        self.assertGreater(second, first)
        self.assertGreaterEqual(second - first, 0.15)

    def test_a_snapshot_without_the_attribute_keeps_the_message_value(self):
        ws, _ = _world(age_s=0.25)
        doc = world_state_to_dict(ws)
        self.assertAlmostEqual(doc["objects"][0]["pose_age_s"], 0.25, places=3)


class TestStaleWorldRejection(unittest.TestCase):

    def _constraints(self, max_age):
        return Constraints(
            frozenset(("OBSERVE", "PICK", "PLACE", "VERIFY", "WAIT", "ABORT")),
            1, 0.06, "demo_slow", max_age)

    def _goal(self):
        return TaskGoal("g", "s", (("target_box_a", "zone_1"),))

    def _decision(self, action="PICK", target="target_box_a"):
        return Decision(action=action, target=target)

    def test_expired_world_is_rejected_with_the_stale_code(self):
        ws, elapsed = _world(age_s=0.0, sample_age_s=5.0)
        env = serialize_envelope(ws, sampled_monotonic=time.monotonic() - elapsed)
        import json
        ok, reason = validate(self._decision(), self._goal(), json.loads(env),
                              self._constraints(2.0))
        self.assertFalse(ok)
        self.assertEqual(reason, STALE_WORLD)

    def test_fresh_world_passes_the_same_gate(self):
        ws, elapsed = _world(age_s=0.0, sample_age_s=0.0)
        env = serialize_envelope(ws, sampled_monotonic=time.monotonic() - elapsed)
        import json
        ok, reason = validate(self._decision(), self._goal(), json.loads(env),
                              self._constraints(2.0))
        self.assertTrue(ok, reason)

    def test_zero_bound_keeps_the_historical_opt_out(self):
        ws, elapsed = _world(age_s=0.0, sample_age_s=99.0)
        env = serialize_envelope(ws, sampled_monotonic=time.monotonic() - elapsed)
        import json
        ok, reason = validate(self._decision(), self._goal(), json.loads(env),
                              self._constraints(0.0))
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main()
