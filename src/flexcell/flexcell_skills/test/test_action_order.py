"""P1-C: illegal action order never reaches the skill dispatch path."""
import unittest

from flexcell_skills.contracts.safety_gate import rejection_canonical_code, validate
from flexcell_skills.contracts.error_codes import ERR_SAFETY_REJECTED
from flexcell_skills.decision_policy import Constraints, Decision, HistoryRecord, TaskGoal

ACTIONS = frozenset(("OBSERVE", "PICK", "PLACE", "VERIFY", "WAIT", "ABORT"))


def _constraints(max_age=0.0):
    return Constraints(ACTIONS, 1, 0.06, "demo_slow", max_age)


def _goal():
    return TaskGoal("g", "s", (("target_box_a", "zone_1"),))


def _world(engaged=False, carried=""):
    return {
        "WorldStateSchemaVersion": 2,
        "world_state": {
            "revision": 1,
            "source": "SIMULATION_GROUND_TRUTH",
            "objects": [{"name": "target_box_a", "klass": "box",
                         "available": True, "pose_age_s": 0.0}],
            "carry": {"engaged": engaged, "object_id": carried,
                      "offset": [0.0, 0.0, -0.16], "reference_frame": "world"},
            "zones": [],
            "robot": {"ee_frame": "end_effector_link"},
        },
        "task_context": {},
    }


def _hist(action, target="target_box_a", outcome=0):
    return HistoryRecord(action=action, target=target, outcome=outcome,
                         error_code=0, attempt=1, world_revision=1,
                         evidence_id="e")


class TestActionOrder(unittest.TestCase):

    def test_place_without_a_successful_pick_is_rejected(self):
        ok, reason = validate(Decision(action="PLACE", target="target_box_a"),
                              _goal(), _world(engaged=True, carried="target_box_a"),
                              _constraints(), ())
        self.assertFalse(ok)
        self.assertEqual(reason, "place_without_pick")

    def test_place_after_a_failed_pick_is_still_rejected(self):
        history = (_hist("PICK", outcome=1),)
        ok, reason = validate(Decision(action="PLACE", target="target_box_a"),
                              _goal(), _world(engaged=True, carried="target_box_a"),
                              _constraints(), history)
        self.assertFalse(ok)
        self.assertEqual(reason, "place_without_pick")

    def test_place_after_a_successful_pick_is_allowed(self):
        history = (_hist("PICK"),)
        ok, reason = validate(Decision(action="PLACE", target="target_box_a"),
                              _goal(), _world(engaged=True, carried="target_box_a"),
                              _constraints(), history)
        self.assertTrue(ok, reason)

    def test_verify_without_a_successful_place_is_rejected(self):
        history = (_hist("PICK"),)
        ok, reason = validate(Decision(action="VERIFY", target="target_box_a"),
                              _goal(), _world(), _constraints(), history)
        self.assertFalse(ok)
        self.assertEqual(reason, "verify_without_place")

    def test_verify_after_a_resume_observe_is_allowed(self):
        # a resumed session may verify an object a previous session left at its
        # goal; the successful OBSERVE is the executor-accepted evidence.
        history = (_hist("OBSERVE"),)
        ok, reason = validate(Decision(action="VERIFY", target="target_box_a"),
                              _goal(), _world(), _constraints(), history)
        self.assertTrue(ok, reason)

    def test_verify_with_no_history_at_all_is_rejected(self):
        ok, reason = validate(Decision(action="VERIFY", target="target_box_a"),
                              _goal(), _world(), _constraints(), ())
        self.assertFalse(ok)
        self.assertEqual(reason, "verify_without_place")

    def test_verify_after_a_successful_place_is_allowed(self):
        history = (_hist("PICK"), _hist("PLACE"))
        ok, reason = validate(Decision(action="VERIFY", target="target_box_a"),
                              _goal(), _world(), _constraints(), history)
        self.assertTrue(ok, reason)

    def test_second_pick_while_still_carried_is_rejected(self):
        history = (_hist("PICK"),)
        ok, reason = validate(Decision(action="PICK", target="target_box_a"),
                              _goal(), _world(engaged=True, carried="target_box_a"),
                              _constraints(), history)
        self.assertFalse(ok)
        self.assertIn(reason, ("already_carried", "pick_while_carried"))

    def test_pick_after_the_object_was_placed_is_allowed(self):
        history = (_hist("PICK"), _hist("PLACE"), _hist("VERIFY"))
        ok, reason = validate(Decision(action="PICK", target="target_box_a"),
                              _goal(), _world(), _constraints(), history)
        self.assertTrue(ok, reason)

    def test_without_history_the_legacy_contract_is_unchanged(self):
        # callers that do not pass history keep the previous behaviour
        ok, reason = validate(Decision(action="PLACE", target="target_box_a"),
                              _goal(), _world(engaged=True, carried="target_box_a"),
                              _constraints())
        self.assertTrue(ok, reason)

    def test_order_reasons_are_typed_in_the_canonical_vocabulary(self):
        for reason in ("place_without_pick", "verify_without_place",
                       "pick_while_carried"):
            with self.subTest(reason=reason):
                self.assertEqual(rejection_canonical_code(reason),
                                 ERR_SAFETY_REJECTED)


if __name__ == "__main__":
    unittest.main()
