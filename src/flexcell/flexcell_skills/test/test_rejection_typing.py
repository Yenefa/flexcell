"""P1-B: a safety rejection keeps its typed cause end to end."""
import unittest

from flexcell_skills.contracts.error_codes import (
    ERR_INTERNAL, ERR_INVALID_GOAL, ERR_NOT_CARRIED, ERR_OBJECT_NOT_FOUND,
    ERR_SAFETY_REJECTED, ERR_STALE_WORLD)
from flexcell_skills.contracts.safety_gate import rejection_canonical_code


class TestRejectionTyping(unittest.TestCase):

    def test_each_documented_reason_maps_to_its_own_code(self):
        expected = {
            "action_not_allowed": ERR_SAFETY_REJECTED,
            "unknown_target": ERR_INVALID_GOAL,
            "world_required": ERR_STALE_WORLD,
            "world_stale": ERR_STALE_WORLD,
            "target_not_available": ERR_OBJECT_NOT_FOUND,
            "already_carried": ERR_SAFETY_REJECTED,
            "not_carried": ERR_NOT_CARRIED,
            "destination_occupied:target_box_b": ERR_SAFETY_REJECTED,
            "destination_geometry_unavailable": ERR_SAFETY_REJECTED,
        }
        for reason, code in expected.items():
            with self.subTest(reason=reason):
                self.assertEqual(rejection_canonical_code(reason), code)

    def test_distinct_causes_stay_distinguishable(self):
        # the audit finding: every rejection used to surface as
        # ERR_SAFETY_REJECTED, so a caller could not tell a stale world from a
        # contract violation.
        stale = rejection_canonical_code("world_stale")
        missing = rejection_canonical_code("target_not_available")
        invalid = rejection_canonical_code("unknown_target")
        violation = rejection_canonical_code("action_not_allowed")
        self.assertEqual(len({stale, missing, invalid, violation}), 4)

    def test_unknown_reason_falls_back_to_internal(self):
        self.assertEqual(rejection_canonical_code("something_new"), ERR_INTERNAL)
        self.assertEqual(rejection_canonical_code(None), ERR_INTERNAL)

    def test_reason_suffix_is_ignored_for_the_code_but_kept_by_the_caller(self):
        self.assertEqual(rejection_canonical_code("destination_occupied:box"),
                         rejection_canonical_code("destination_occupied"))


class TestDecisionLogCarriesTheTypedCause(unittest.TestCase):

    def test_rejection_record_exposes_kind_and_canonical_code(self):
        import json
        import tempfile
        from pathlib import Path
        from flexcell_skills.common import JsonlLog

        class _Node:
            def get_logger(self):
                return type("L", (), {
                    "info": staticmethod(lambda *a, **k: None),
                    "warn": staticmethod(lambda *a, **k: None),
                    "error": staticmethod(lambda *a, **k: None)})()

        tmp = tempfile.mkdtemp(prefix="rej_")
        log = JsonlLog(_Node(), tmp, "decisions.jsonl")
        # the exact fields the executor writes on a gate rejection
        gate_reason = "world_stale"
        rejection_code = rejection_canonical_code(gate_reason)
        rejection_kind = str(gate_reason).split(":", 1)[0]
        log.write({"dispatched": False, "safety_rejection": gate_reason,
                   "rejection_kind": rejection_kind,
                   "rejection_error_code": int(rejection_code)})
        doc = json.loads((Path(tmp) / "decisions.jsonl").read_text().splitlines()[-1])
        self.assertEqual(doc["rejection_kind"], "world_stale")
        self.assertEqual(doc["rejection_error_code"], ERR_STALE_WORLD)
        self.assertFalse(doc["dispatched"])


if __name__ == "__main__":
    unittest.main()
