"""P2-B: one builder owns the decision-log shape."""
import unittest

from flexcell_skills.contracts.decision_record import decision_record
from flexcell_skills.decision_policy import Decision


def _rec(dispatched=True, **over):
    kwargs = dict(run_id="r", scenario="s", seq=1, previous_skill_result=None,
                  recovery=None,
                  decision=Decision(action="PICK", target="target_box_a"),
                  policy_name="fsm", policy_version="1.0", world_revision=3,
                  observe_evidence_id="ev", decide_latency_ms=0.5,
                  dispatched=dispatched)
    kwargs.update(over)
    return decision_record(**kwargs)


class TestDecisionRecord(unittest.TestCase):

    def test_a_dispatched_record_has_no_rejection_fields(self):
        record = _rec()
        self.assertTrue(record["dispatched"])
        self.assertIsNone(record["safety_rejection"])
        self.assertNotIn("rejection_kind", record)
        self.assertNotIn("rejection_error_code", record)

    def test_a_rejection_carries_both_typed_fields(self):
        record = _rec(dispatched=False, rejection_kind="world_stale",
                      rejection_error_code=34)
        self.assertFalse(record["dispatched"])
        self.assertEqual(record["safety_rejection"], "world_stale")
        self.assertEqual(record["rejection_kind"], "world_stale")
        self.assertEqual(record["rejection_error_code"], 34)

    def test_a_rejection_without_a_reason_is_refused(self):
        # the gate must never record a silent rejection
        with self.assertRaises(ValueError):
            _rec(dispatched=False)

    def test_the_audit_fields_both_sites_need_are_always_present(self):
        required = ("run_id", "scenario_id", "seq", "previous_skill_result",
                    "recovery", "action", "target", "confidence",
                    "reason_code", "explanation", "policy", "policy_version",
                    "world_revision", "observe_evidence_id",
                    "decide_latency_ms", "policy_trace", "dispatched",
                    "safety_rejection")
        for record in (_rec(), _rec(dispatched=False, rejection_kind="unknown_target",
                                    rejection_error_code=1)):
            for key in required:
                with self.subTest(key=key):
                    self.assertIn(key, record)

    def test_the_action_and_target_are_the_sanitised_dispatch_view(self):
        # explanation is logged but never becomes part of the dispatch identity
        record = _rec(decision=Decision(action="PICK", target="target_box_a",
                                        explanation="rm -rf /"))
        self.assertEqual(record["action"], "PICK")
        self.assertEqual(record["target"], "target_box_a")
        self.assertEqual(record["explanation"], "rm -rf /")

    def test_the_builder_is_pure(self):
        first = _rec()
        second = _rec()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
