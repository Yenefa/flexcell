import unittest

from flexcell_capabilities.contact_stroke import (
    COMPACT_MOTION_GOALS, STANDARD_MOTION_GOALS, stroke_checkpoints,
)


class ContactStrokeTest(unittest.TestCase):
    def test_compact_keeps_contact_acquisition_and_reserves_unload_and_return(self):
        standard = stroke_checkpoints(.03, STANDARD_MOTION_GOALS)
        compact = stroke_checkpoints(.03, COMPACT_MOTION_GOALS)
        self.assertEqual(compact[:2], standard[:2])
        self.assertAlmostEqual(compact[-1], standard[-1])
        self.assertAlmostEqual(compact[-1], .035)
        self.assertLessEqual(max(b - a for a, b in zip(compact, compact[1:])), .0080000001)
        self.assertEqual(2 + len(compact) + 2, 10)

    def test_unsupported_cap_has_no_fallback_to_a_larger_actuator_budget(self):
        with self.assertRaises(ValueError):
            stroke_checkpoints(.03, 9)
